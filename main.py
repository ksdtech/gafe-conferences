"""`main` is the top level module for your Flask application."""

from datetime import date, datetime, timedelta
from dateutil import parser as date_parser
import json
import logging
import os
import pytz
import six

# Import Flask Framework modules
from flask import Flask, flash, request, redirect, render_template, session, url_for
from flask_login import LoginManager, current_user, login_user, logout_user

# Impprt Googley modules
from oauth2client.client import OAuth2WebServerFlow, OAuth2Credentials
from oauth2client.appengine import AppAssertionCredentials

# Applicaition-specific modules
from models import User, Booking, RemindersToken
from forms import UserPrefsForm, DayPrefsForm, BookingForm, RemindersForm


# Flask setup
app = Flask(__name__)

# Determine GAE enironment and load private config
if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    app.config['GAE_SERVER'] = 'dev_appserver'
    from config_dev import (debug as app_debug, log_level, gafe_domain, hostname, port, protocol, secret_key,
        friendly_name, support_email, reminders_expire)
else:
    app.config['GAE_SERVER'] = 'appengine'
    from config_gae import (debug as app_debug, log_level, gafe_domain, hostname, port, protocol, secret_key,
        friendly_name, support_email, reminders_expire)
server_name = '%s:%d' % (hostname, port) if ((protocol == 'http' and port != 80) or (protocol == 'https' and port != 443)) else hostname


# Flask built-in configs
app.config['DEBUG'] = app_debug
app.config['PREFERRED_URL_SCHEME'] = protocol
app.config['SERVER_NAME'] = server_name
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_COOKIE_NAME'] = '_conf_sessions_'


# Our stuff
app.config['LOG_LEVEL'] = log_level
app.config['FRIENDLY_NAME'] = friendly_name
app.config['SUPPORT_EMAIL'] = support_email
app.config['REMINDERS_EXPIRE'] = reminders_expire


# Google OAuth2 setup
secrets = None
with open('client_secrets.json') as f:
    secrets = json.load(f)['web']

app.config['OAUTH2CALLBACK_PATH'] = '/oauth2callback'
app.config['GOOGLE_CLIENT_ID'] = secrets['client_id']
app.config['GOOGLE_CLIENT_SECRET'] = secrets['client_secret']
app.config['GOOGLE_LOGIN_REDIRECT_URI'] = '%s://%s%s' % (
    app.config['PREFERRED_URL_SCHEME'],
    app.config['SERVER_NAME'], 
    app.config['OAUTH2CALLBACK_PATH'])
app.config['GOOGLE_LOGIN_DOMAIN'] = gafe_domain
app.config['GOOGLE_LOGIN_SCOPE'] = ' '.join([
    'email',
    'profile',
    'https://www.googleapis.com/auth/plus.login',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
])
app.config['GOOGLE_SERVICE_ACCOUNT_SCOPE'] = ' '.join([
    'email',
    'profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
])


# Flask-Login setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    user = User.getById(user_id)

    # logging.debug('LOAD USER: %s, got %r' (user_id, user))
    return user


# Google OAuth2 setup for user logins
flow = OAuth2WebServerFlow(
    app.config['GOOGLE_CLIENT_ID'],
    app.config['GOOGLE_CLIENT_SECRET'],
    app.config['GOOGLE_LOGIN_SCOPE'],
    redirect_uri=app.config['GOOGLE_LOGIN_REDIRECT_URI'],
    hd=app.config['GOOGLE_LOGIN_DOMAIN'],
    approval_prompt='force')

# Google OAuth2 setup for service accounts, if we ever need to use it
# app.config['service_account_credentials'] = AppAssertionCredentials(
#     app.config['GOOGLE_SERVICE_ACCOUNT_SCOPE'])


# Flags for booking availabilty
SLOT_AVAILABLE = 0
SLOT_OFF_SCHEDULE = 1
SLOT_BUSY = 2
SLOT_BOOKED = 3

# Additional flag if it's too early or late to book
SLOT_DEADLINE = 8


# Flask helper functions
@app.context_processor
def utility_processor():
    def date_format_local(dt_start, day_of_week=True):
        return dt_start.strftime('%A %b %-d, %Y' if day_of_week else '%b %-d, %Y')

    def date_format_from_utc(dt_start_utc, tz):
        if isinstance(tz, six.string_types):
            tz = pytz.timezone(tz)
        dt_start = pytz.utc.localize(dt_start_utc).astimezone(tz)
        return date_format_local(dt_start)

    def time_format_local(dt_start, dt_end):
        return '%s - %s' % (dt_start.strftime('%I:%M %p').lstrip('0'), 
            dt_end.strftime('%I:%M %p').lstrip('0'))

    def time_format_from_utc(dt_start_utc, dt_end_utc, tz):
        if isinstance(tz, six.string_types):
            tz = pytz.timezone(tz)
        dt_start = pytz.utc.localize(dt_start_utc).astimezone(tz)
        dt_end = pytz.utc.localize(dt_end_utc).astimezone(tz)
        return time_format_local(dt_start, dt_end)

    def time_range(d, t, tz, duration):
        dt_start = tz.localize(datetime.combine(d, t))
        dt_end = dt_start + timedelta(minutes=duration)
        return time_format_local(dt_start, dt_end)

    def slot_at(slots, d, t, tz):
        status = SLOT_OFF_SCHEDULE
        dt_start = tz.localize(datetime.combine(d, t))
        for s in slots:
            if s['start'] == dt_start:
                status = SLOT_AVAILABLE if s['available'] else SLOT_BUSY
        return status

    return dict(date_format_local=date_format_local,
        date_format_from_utc=date_format_from_utc,
        time_format_local=time_format_local,
        time_format_from_utc=time_format_from_utc,
        time_range=time_range, 
        slot_at=slot_at)


def flash_form_errors(msg, form):
    flash(msg + ' Please correct these fields and re-submit.', 'error')
    for field, errors in form.errors.items():
        for error in errors:
            flash('> %s: %s' % (getattr(form, field).label.text, error), 'error')


# Flask routes
@app.route('/')
def index():
    return render_template('index.html', user=current_user)

@app.route('/login')
def login():
    authorize_url = flow.step1_get_authorize_url()
    return redirect(authorize_url)

@app.route('/logout')
def logout():
    logout_user()
    flash('You were logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/prefs', methods=['GET', 'POST'])
def prefs():
    user = current_user
    if user.is_active and not user.is_anonymous and user.auth_type == 'gafe':
        form = UserPrefsForm(obj=user.prefs)
        if request.method == 'POST':
            if form.validate_on_submit():
                form.populate_obj(user.prefs)
                user.put()

                flash('Your preferences were updated.', 'info')
                return redirect(url_for('index'))
            else:
                flash_form_errors('Your preferences could not be updated.', form)

        tz = user.getTimezoneObject()
        today = date.today()
        next_week = today + timedelta(days=7)
        dt_today = tz.localize(
            datetime(today.year, today.month, today.day, 0, 0, 0, 0))
        dt_next_week = tz.localize(
            datetime(next_week.year, next_week.month, next_week.day, 0, 0, 0, 0))
        return render_template('prefs.html', form=form, user=user, 
                dt_today=dt_today, dt_next_week=dt_next_week)

    flash('Access denied.  Please log in via Google Apps.', 'error')
    return redirect(url_for('index'))

@app.route('/times', methods=['GET', 'POST'])
def times():
    user = current_user
    if user.is_active and not user.is_anonymous and user.auth_type == 'gafe':
        form = DayPrefsForm(obj=user)
        if request.method == 'POST':
            if form.validate_on_submit():
                form.populate_obj(user)
                user.put()

                flash('Your preferences were updated.', 'info')
                return redirect(url_for('index'))
            else:
                flash_form_errors('Your preferences could not be updated.', form)
        return render_template('times.html', user=user, form=form)

    flash('Access denied.  Please log in via Google Apps.', 'error')
    return redirect(url_for('index'))

@app.route('/bookings')
def bookings():
    user = current_user
    if user.is_active and not user.is_anonymous and user.auth_type == 'gafe':
        bookings = Booking.getBookingsForResource(user)
        return render_template('user-bookings.html', bookings=bookings)

    flash('Access denied.  Please log in via Google Apps.', 'error')
    return redirect(url_for('index'))

@app.route('/resources')
def resources():
    resources = User.getAvailableResources()
    return render_template('resources.html', resources=resources)

@app.route('/calendar/<uid>')
@app.route('/calendar/<uid>/<date_str>')
def calendar(uid, date_str=None):
    resource = User.getByUrlsafeId(uid)
    tz = resource.getTimezoneObject()
    slots = resource.getAvailableSlots()
    limits = resource.getSlotLimits(slots, True)

    d = date.today()
    if date_str is None:
        if len(limits['dates']) > 0:
            d = limits['dates'][0]
    else:
        d = date_parser.parse(date_str).date()

    day_offset = d.weekday()
    d -= timedelta(days=day_offset)
    week_prev = d - timedelta(days=7)
    week_next = d + timedelta(days=7)
    date_str = d.strftime('%Y-%m-%d')
    date_prev = week_prev.strftime('%Y-%m-%d')
    date_next = week_next.strftime('%Y-%m-%d')

    limits['week_start'] = d
    week_dates = [ ]
    while d < week_next:
        if d in limits['dates']:
            week_dates.append(d)
        d += timedelta(days=1)
    limits['week_dates'] = week_dates
    return render_template('calendar.html', uid=uid, date_str=date_str, 
        date_prev=date_prev, date_next=date_next,
        resource=resource, duration=resource.prefs.duration, tz=tz,
        slots=slots, limits=limits)

@app.route('/booking/<uid>/<date_str>/<time_str>', methods=['GET', 'POST'])
def booking(uid, date_str, time_str):
    resource = User.getByUrlsafeId(uid)
    tz = resource.getTimezoneObject()
    duration = resource.prefs.duration
    dt_str = '%s %s' % (date_str, time_str.replace('-', ':', 1))
    dt_start = tz.localize(date_parser.parse(dt_str))
    dt_end = dt_start + timedelta(minutes=duration)
    form = BookingForm(start_time=dt_start, end_time=dt_end, timezone=tz.zone)
    if request.method == 'POST':
        if form.validate_on_submit():
            booking = Booking.createFromPost(resource, form.data)
            flash('Your booking succeeded.', 'info')
            return redirect(url_for('calendar', uid=uid, date_str=date_str))
        else:
            flash_form_errors('Your booking failed.', form)
    return render_template('booking-new.html', 
        uid=uid, date_str=date_str, time_str=time_str, 
        form=form, resource=resource, 
        dt_start=dt_start, tz=tz, duration=duration)

@app.route('/reminders/<token>')
@app.route('/reminders', methods=['GET', 'POST'])
def reminders(token=None):
    if token:
        email = RemindersToken.validateToken(token)
        if email:
            bookings = Booking.getBookingsForAttendeeEmail(email)
            return render_template('attendee-bookings.html', email=email, bookings=bookings)
        else:
            flash('Token invalid or expired', 'error')

    form = RemindersForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            RemindersToken.createAndSendToken(form.email.data, 
                url_for('reminders', _external=True), app.config)

            flash('Please check your email inbox for a message', 'info')
            return redirect(url_for('index'))

    return render_template('reminders.html', form=form)


# Special route for OAuth2 login (step 1)
# Must match the "redirect URI" in the Google console/client_secrets.json file
@app.route(app.config['OAUTH2CALLBACK_PATH'])
def oauth2callback():
    error = request.args.get('error', None)
    code = request.args.get('code', None)

    # logging.debug('CODE: %s' % code)
    if error is not None or code is None:
        if error == 'access_denied':
            error = 'The user denied access.'
        elif error is not None:
            error = 'The error was "' + error + '".'
        else:
            error = 'An error occurred: no code was returned from consent screen.'
        flash('Login was not completed. %s' % error, 'error')
        return redirect(url_for('index'))
 
    credentials = flow.step2_exchange(code)

    # logging.debug('ACCESS_TOKEN: %s' % credentials.access_token)
    user, create = User.fromCredentials(credentials)

    # logging.debug('USER: %s' % user.get_id())
    login_user(user, force=True, fresh=True)
    flash('You were logged in.', 'info')
    return redirect(url_for('index'))


# See the section on <a href="/appengine/docs/python/#Python_App_caching">Requests and App Caching</a> for information on how
# App Engine reuses your request handlers when you specify a main function
def main():
    # Set the logging level in the main function
    level = { 'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG }.get(app.config['LOG_LEVEL'], 
            logging.DEBUG if app.config['DEBUG'] else logging.INFO)

    logging.getLogger().setLevel(level)
    logging.info('MAIN: server is %s' % app.config['GAE_SERVER'])
    logging.info(' log level %d' % level)
    logging.info(' debug %r' % app.config['DEBUG'])
    app.run(host=app.config['HOSTNAME'], port=app.config['PORT'])


# Start the app locally, based on settings in config.py
if __name__ == '__main__':
    main()


