from flask import (
    Blueprint,
    redirect,
    request,
    flash,
    url_for,
    render_template,
    send_from_directory)
from flask_login import (
    login_required,
    login_user,
    current_user,
    logout_user)

from sqlalchemy import text

from lib.safe_next_url import safe_next_url
from dataweb.blueprints.user.decorators import anonymous_required
from dataweb.blueprints.user.models import User, File
from dataweb.blueprints.user.forms import (
    LoginForm,
    BeginPasswordResetForm,
    PasswordResetForm,
    SignupForm,
    WelcomeForm,
    UpdateCredentialsForm,
    LookUpForm,
    FileBulkDeleteForm)#UpdateLocaleForm

user = Blueprint('user', __name__, template_folder='templates')


@user.route('/login', methods=['GET', 'POST'])
@anonymous_required()
def login():
    form = LoginForm(next=request.args.get('next'))

    if form.validate_on_submit():
        u = User.find_by_identity(request.form.get('identity'))

        if u and u.authenticated(password=request.form.get('password')):
            # As you can see remember me is always enabled, this was a design
            # decision I made because more often than not users want this
            # enabled. This allows for a less complicated login form.
            #
            # If however you want them to be able to select whether or not they
            # should remain logged in then perform the following 3 steps:
            # 1) Replace 'True' below with: request.form.get('remember', False)
            # 2) Uncomment the 'remember' field in user/forms.py#LoginForm
            # 3) Add a checkbox to the login form with the id/name 'remember'
            if u.is_active() and login_user(u, remember=True):
                u.update_activity_tracking(request.remote_addr)

                # Handle optionally redirecting to the next URL safely.
                next_url = request.form.get('next')
                if next_url:
                    return redirect(safe_next_url(next_url))

                return redirect(url_for('user.settings'))
            else:
                flash('This account has been disabled.', 'error')
        else:
            flash('Identity or password is incorrect.', 'error')

    return render_template('user/login.html', form=form)


@user.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('user.login'))


@user.route('/account/begin_password_reset', methods=['GET', 'POST'])
@anonymous_required()
def begin_password_reset():
    form = BeginPasswordResetForm()

    if form.validate_on_submit():
        u = User.initialize_password_reset(request.form.get('identity'))

        flash('An email has been sent to {0}.'.format(u.email), 'success')
        return redirect(url_for('user.login'))

    return render_template('user/begin_password_reset.html', form=form)


@user.route('/account/password_reset', methods=['GET', 'POST'])
@anonymous_required()
def password_reset():
    form = PasswordResetForm(reset_token=request.args.get('reset_token'))

    if form.validate_on_submit():
        u = User.deserialize_token(request.form.get('reset_token'))

        if u is None:
            flash('Your reset token has expired or was tampered with.',
                  'error')
            return redirect(url_for('user.begin_password_reset'))

        form.populate_obj(u)
        u.password = User.encrypt_password(request.form.get('password'))
        u.save()

        if login_user(u):
            flash('Your password has been reset.', 'success')
            return redirect(url_for('user.settings'))

    return render_template('user/password_reset.html', form=form)


@user.route('/signup', methods=['GET', 'POST'])
@anonymous_required()
def signup():
    form = SignupForm()

    if form.validate_on_submit():
        u = User()

        form.populate_obj(u)
        u.password = User.encrypt_password(request.form.get('password'))
        u.save()

        if login_user(u):
            flash('Awesome, thanks for signing up!', 'success')
            return redirect(url_for('user.welcome'))

    return render_template('user/signup.html', form=form)


@user.route('/welcome', methods=['GET', 'POST'])
@login_required
def welcome():
    if current_user.username:
        flash('You already picked a username.', 'warning')
        return redirect(url_for('user.settings'))

    form = WelcomeForm()

    if form.validate_on_submit():
        current_user.username = request.form.get('username')
        current_user.save()

        flash('Sign up is complete, enjoy our services.', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/welcome.html', form=form)


@user.route('/settings')
@login_required
def settings():
    return render_template('user/settings.html')
# LookUpFiles -----------------------------------------------------------------------
@user.route('/lookup', defaults={'page': 1})
@user.route('/lookup/page/<int:page>')
def files(page):
    lookup_form = LookUpForm()
    bulk_form = FileBulkDeleteForm()

    sort_by = File.sort_by(request.args.get('sort', 'created_on'),
                           request.args.get('direction', 'desc'))
    order_values = '{0} {1}'.format(sort_by[0], sort_by[1])

    paginated_files = File.query \
        .filter(File.file_search(request.args.get('q', text('')))) \
        .order_by(File.created_on, text(order_values)) \
        .paginate(page, 50, True) 

    return render_template('user/lookup.html',
                           form=lookup_form, bulk_form=bulk_form,
                           files=paginated_files)

@user.route('/lookup/files_bulk_delete', methods=['POST'])
def files_bulk_delete():
    form = FileBulkDeleteForm()

    if form.validate_on_submit():
        ids = User.get_bulk_action_ids(request.form.get('scope'),
                                       request.form.getlist('bulk_ids'),
                                       query=request.args.get('q', text('')))

        # Prevent circular imports.
        from dataweb.blueprints.user.tasks import delete_files

        delete_files.delay(ids)

        flash('{0} files(s) were scheduled to be deleted.'.format(len(ids)),
              'success')
    else:
        flash('No files were deleted, something went wrong.', 'error')

    return redirect(url_for('user.files'))


@user.route('/lookup/download_to_browser/<int:id>')
def download_to_browser(id):
    file = File.query.get(id)
    file_name = file.filename + '.csv'
    directory = 'DataFiles/'
    return send_from_directory(directory, file_name, as_attachment=True)


@user.route('/settings/update_credentials', methods=['GET', 'POST'])
@login_required
def update_credentials():
    form = UpdateCredentialsForm(obj=current_user)

    if form.validate_on_submit():
        new_password = request.form.get('password', '')
        current_user.email = request.form.get('email')

        if new_password:
            current_user.password = User.encrypt_password(new_password)

        current_user.save()

        flash('Your sign in settings have been updated.', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/update_credentials.html', form=form)

'''
@user.route('/settings/update_locale', methods=['GET', 'POST'])
@login_required
def update_locale():
    form = UpdateLocaleForm(locale=current_user.locale)

    if form.validate_on_submit():
        form.populate_obj(current_user)
        current_user.save()

        flash('Your locale settings have been updated.', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/update_locale.html', form=form)
'''