import base64
from datetime import date, datetime, timedelta
from dateutil import parser as date_parser
import httplib2
import pytz

from flask import render_template

from google.appengine.api import mail, memcache
from google.appengine.ext import ndb
from apiclient import discovery
from oauth2client.appengine import CredentialsNDBProperty

from flask_login import UserMixin, make_secure_token


def conflict(slot, busy_events):
    return any(e['dt_start'] < slot['end'] and e['dt_end'] > slot['start'] for e in busy_events)


# User 1:1 UserPrefs
class UserPrefs(ndb.Model):
    title = ndb.StringProperty(required=True, default='Parent-Teacher Conferences')
    display_name = ndb.StringProperty()
    location = ndb.StringProperty()
    timezone = ndb.StringProperty(required=True, default='America/Los_Angeles')
    interval = ndb.IntegerProperty(required=True, default=30)
    duration = ndb.IntegerProperty(required=True, default=20)
    first_day_scheduled = ndb.DateProperty()
    last_day_scheduled = ndb.DateProperty()
    booking_start_date = ndb.DateProperty()
    booking_start_time = ndb.StringProperty()
    booking_end_date = ndb.DateProperty()
    booking_end_time = ndb.StringProperty()
    minimum_notice_hours = ndb.IntegerProperty(required=True, default=36)
    weekday_start = ndb.IntegerProperty(required=True, default=1)

# User 1:7 DayPrefs
class DayPrefs(ndb.Model):
    position = ndb.IntegerProperty(required=True)
    enabled = ndb.BooleanProperty(required=True)
    day_start_time = ndb.StringProperty(required=True)
    lunch_start_time = ndb.StringProperty(required=True)
    lunch_end_time = ndb.StringProperty(required=True)
    day_end_time = ndb.StringProperty(required=True)

class User(ndb.Model, UserMixin):
    credentials = CredentialsNDBProperty()
    auth_type = ndb.StringProperty()
    email = ndb.StringProperty()
    first_name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    google_id = ndb.StringProperty()
    access_token = ndb.StringProperty()
    refresh_token = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    deleted = ndb.DateTimeProperty()
    prefs = ndb.StructuredProperty(UserPrefs)
    days = ndb.StructuredProperty(DayPrefs, repeated=True)

    @property
    def is_active(self):
        return self.deleted is None

    def booking_is_available(self, dt=None):
        if not self.is_active:
            return False
        if dt is None:
            dt = datetime.now()
        dt_start = self.prefs.booking_start_time or dt
        dt_end = self.prefs.booking_end_time or dt
        return dt_start <= dt and dt <= dt_end

    def get_id(self):
        return self.key.id()

    def getTimezoneObject(self):
        return pytz.timezone(self.prefs.timezone)

    def defaultUserPrefs(self):
        display_name = ' '.join([self.first_name, self.last_name])
        title = 'Parent-Teacher Conferences with %s' % display_name
        prefs = UserPrefs(title=title, display_name=display_name)
        return prefs

    def defaultDayPrefs(self):
        day_prefs = [ ]
        
        # Per Python's weekday() function, Monday is 0, Sunday is 6
        for position in range(7):
            enabled = position <= 4 # Monday through Friday
            day_pref = DayPrefs(position=position, enabled=enabled)
            day_pref.day_start_time = '07:00'
            day_pref.lunch_start_time = '08:15'
            day_pref.lunch_end_time = '12:30'
            day_pref.day_end_time = '16:30'
            day_prefs.append(day_pref)
        return day_prefs

    def getBusyEvents(self, dt_from, dt_to, calendar_id='primary'):
        http_auth = httplib2.Http(memcache)
        self.credentials.authorize(http_auth)
        cal_service = discovery.build("calendar", "v3", http=http_auth)
        busy_events = [ ]
        page_token = None

        # print "GET BUSY ", dt_from
        while True:
            result = cal_service.events().list(
                calendarId=calendar_id, 
                orderBy='startTime',
                singleEvents=True,
                timeMin=dt_from.isoformat(),
                timeMax=dt_to.isoformat(),
                timeZone=self.prefs.timezone,
                pageToken=page_token).execute()
            events = result['items']

            # print "EVENTS: ", events
            for e in events:
                if e.get('transparency') != 'transparent':
                    dt_start = date_parser.parse(e['start']['dateTime'])
                    dt_end = date_parser.parse(e['end']['dateTime'])
                    e.update({ 'dt_start': dt_start, 'dt_end': dt_end })
                    busy_events.append(e)
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        return busy_events

    def getPossibleSlotsForDay(self, d):
        slots = [ ]
        tz = self.getTimezoneObject()
        d_start = self.prefs.first_day_scheduled or d
        d_end = self.prefs.last_day_scheduled or d
        if d_start <= d and d <= d_end:
            i = d.weekday()
            day_prefs = self.days[i]
            if day_prefs.enabled:
                day_start = tz.localize(
                    date_parser.parse(day_prefs.day_start_time or '04:00').replace(
                    year=d.year, month=d.month, day=d.day))
                day_end = tz.localize(
                    date_parser.parse(day_prefs.day_end_time or '23:00').replace(
                    year=d.year, month=d.month, day=d.day))
                lunch_start = None
                lunch_end = None
                if day_prefs.lunch_start_time and day_prefs.lunch_end_time:
                    lunch_start = tz.localize(
                        date_parser.parse(day_prefs.lunch_start_time).replace(
                        year=d.year, month=d.month, day=d.day))
                    lunch_end = tz.localize(
                        date_parser.parse(day_prefs.lunch_end_time).replace(
                        year=d.year, month=d.month, day=d.day))
                interval = timedelta(minutes=self.prefs.interval)
                t_start = day_start
                t_end = t_start + interval
                while t_end <= day_end:
                    if not lunch_start or (t_start >= lunch_end or t_end <= lunch_start):
                        t_start_time = t_start.time()
                        slots.append({ 'start': t_start, 'end': t_end, 'available': True })
                    t_start = t_end
                    t_end = t_start + interval
        return slots

    def getPossibleSlots(self, dt_from, dt_to):
        all_slots = [ ]
        d_from = dt_from.date()
        d_to = dt_to.date()
        d = d_from
        while d <= d_to:
            slots = self.getPossibleSlotsForDay(d)
            all_slots += slots
            d += timedelta(days=1)
        return all_slots

    def getSlotLimits(self, slots, available_only=True):
        latest_day = None
        earliest_time = None
        latest_time = None
        dates = [ ]
        times = [ ]
        for s in slots:
            if not available_only or s['available']:
                d = s['start'].date()
                t = s['start'].time()
                if latest_day is None or d != latest_day:
                    dates.append(d)
                    latest_day = d
                if not earliest_time or earliest_time > t:
                    earliest_time = t
                if not latest_time or latest_time < t:
                    latest_time = t
        if latest_day and earliest_time and latest_time:
            interval = timedelta(minutes=self.prefs.interval)
            t = datetime.combine(latest_day, earliest_time)
            t_end = datetime.combine(latest_day, latest_time)
            while t <= t_end:
                times.append(t.time())
                t += interval
        return { 'dates': dates, 'times': times }

    def getAvailableSlots(self, dt_from=None, dt_to=None, calendar_id='primary'):
        # Get some kind of date range
        d_today = date.today()
        day_offset = d_today.weekday()
        d_from = d_today - timedelta(days=day_offset)
        d_to = d_from + timedelta(days=35)
        tz = self.getTimezoneObject()
        if dt_from is None:
            if self.prefs.first_day_scheduled is not None:
                d_from = self.prefs.first_day_scheduled
            dt_from = tz.localize(
                datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0, 0))
        if dt_to is None:
            if self.prefs.last_day_scheduled is not None:
                d_to = self.prefs.last_day_scheduled
            dt_to = tz.localize(
                datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0, 0))

        slots = self.getPossibleSlots(dt_from, dt_to)
        busy_events = self.getBusyEvents(dt_from, dt_to, calendar_id)
        for s in slots:
            s['available'] = not conflict(s, busy_events)
        return slots

    @classmethod
    def getById(cls, user_id):
        try:
            key = ndb.Key('User', user_id)
            return key.get()
        except:
            return None

    @classmethod
    def getByUrlsafeId(cls, uid):
        try:
            key = ndb.Key(urlsafe=uid)
            return key.get()
        except:
            return None

    @classmethod
    def getAvailableResources(cls):
        users = [ ]
        qry = User.query(User.auth_type == 'gafe').order(User.last_name)
        for user in qry.fetch(100):
            if user.booking_is_available():
                users.append(user)
        return users

    @classmethod
    def findUserOrCreateKey(cls, auth_type, email):
        qry = User.query(User.auth_type == auth_type, User.email == email)
        user = qry.get()
        if user is not None:
            return (user, False)
        prefix, domain = email.split('@')
        timestr = datetime.utcnow().isoformat()
        token = make_secure_token(email, timestr)[8:32]
        new_id = '@'.join([prefix, token])
        return (ndb.Key('User', new_id), True)

    @classmethod
    def fromCredentials(cls, credentials):
        http_auth = httplib2.Http(memcache)
        credentials.authorize(http_auth)
        plus_service = discovery.build("plus", "v1", http=http_auth)
        profile = plus_service.people().get(userId='me').execute()
        email = profile['emails'][0]['value'].lower()
        user = None
        user_or_key, create = cls.findUserOrCreateKey('gafe', email)
        if create:
            user = User(key=user_or_key, credentials=credentials)
            user.auth_type = 'gafe'
            user.email = email
            user.first_name = profile['name']['givenName']
            user.last_name = profile['name']['familyName']
            user.google_id = profile['id']
            user.access_token = credentials.access_token
            user.refresh_token = credentials.refresh_token
            user.prefs = user.defaultUserPrefs()
            user.days = user.defaultDayPrefs()
            user.put()
        else:
            user = user_or_key
            user.credentials = credentials
            user.put()
        return (user, create)


class Event(ndb.Model):
    location = ndb.StringProperty()
    calendar_id = ndb.StringProperty()
    event_id = ndb.StringProperty()
    url = ndb.StringProperty()

class Attendee(ndb.Model):
    email = ndb.StringProperty()
    phone = ndb.StringProperty()
    first_name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    notes = ndb.StringProperty() # 1500 char limit

class Booking(ndb.Model):
    resource = ndb.KeyProperty(kind=User)
    title = ndb.StringProperty()
    organizer_name = ndb.StringProperty()
    attendee = ndb.StructuredProperty(Attendee)
    event = ndb.StructuredProperty(Event)
    start_time = ndb.DateTimeProperty()
    end_time = ndb.DateTimeProperty()
    timezone = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)
    reminded = ndb.DateTimeProperty()
    canceled = ndb.DateTimeProperty()

    def sendReminder(self, credentials):
        pass

    def createCalendarEvent(self, resource):
        description = render_template('event-description.txt', resource=resource, booking=self)
        location = resource.prefs.location
        tz = pytz.timezone(self.timezone)
        start_time = pytz.utc.localize(self.start_time).astimezone(tz).isoformat()
        end_time = pytz.utc.localize(self.end_time).astimezone(tz).isoformat()
        event_id = None
        # event_id =  base64.b32encode(self.key.urlsafe()).rstrip('=').lower()

        # print "CREATE EVENT id ", event_id
        # print "CREATE EVENT start ", start_time
        # print "CREATE EVENT end ", end_time
        # print "CREATE EVENT timezone ", self.timezone

        event = {
            'id': event_id,
            'summary': self.title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': self.timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': self.timezone,
            },
            'attendees': [
                { 
                    'email': resource.email,
                    'organizer': True
                },
                { 
                    'email': self.attendee.email 
                } 
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [ 
                    {
                        'method': 'email',
                        'minutes': 1440
                    },
                    {
                        'method': 'popup',
                        'minutes': 30
                    }
                ]
            }
        }

        # make calendar entry
        http_auth = httplib2.Http(memcache)
        resource.credentials.authorize(http_auth)
        cal_service = discovery.build("calendar", "v3", http=http_auth)

        calendar = cal_service.calendars().get(calendarId='primary').execute()
        new_event = cal_service.events().insert(
            calendarId='primary', sendNotifications=True, body=event).execute()
        
        self.event = Event()
        self.event.location = location
        self.event.calendar_id = calendar['id']
        self.event.event_id = new_event['id']
        self.event.url = new_event['htmlLink']

        self.put()

    @classmethod
    def createFromPost(cls, resource, data):
        attendee = Attendee()
        attendee.email = data['email']
        attendee.phone = data['phone']
        attendee.first_name = data['first_name']
        attendee.last_name = data['last_name']
        attendee.notes = data['notes']

        booking = Booking(resource=resource.key, attendee=attendee)
        booking.title = resource.prefs.title
        booking.organizer_name = resource.prefs.display_name
        start_time_utc = date_parser.parse(data['start_time']).astimezone(pytz.utc).replace(tzinfo=None)
        end_time_utc = date_parser.parse(data['end_time']).astimezone(pytz.utc).replace(tzinfo=None)
 
        # print "CREATE BOOKING start ", start_time_utc
        # print "CREATE BOOKING end ", end_time_utc
        # print "CREATE BOOKING timezone ", data['timezone']

        booking.start_time = start_time_utc
        booking.end_time = end_time_utc
        booking.timezone = data['timezone']
        booking.put()

        try:
            booking.createCalendarEvent(resource)
            # booking.sendReminder(credentials)
        except:
            booking.key.delete()
            booking = None
            raise

        return booking

    @classmethod
    def getBookingsForResource(cls, resource):
        qry = Booking.query(Booking.resource == resource.key).order(Booking.start_time)
        return qry.fetch()

    @classmethod
    def getBookingsForAttendeeEmail(cls, email):
        qry = Booking.query(Booking.attendee.email == email).order(Booking.start_time)
        return qry.fetch()

class RemindersToken(ndb.Model):
    email = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    expires = ndb.DateTimeProperty()

    @classmethod
    def validateToken(cls, token):
        email = None
        try:
            key = ndb.Key(urlsafe=token)
            reminders_token = key.get()
            email = reminders_token.email
            dt_now_utc = datetime.utcnow()
            if reminders_token.expires <= dt_now_utc:
                key.delete()
                email = None
        except:
            pass
        return email

    @classmethod
    def invalidateTokensForEmail(cls, email):
        dt_now_utc = datetime.utcnow()
        qry = RemindersToken.query(ndb.OR(RemindersToken.expires <= dt_now_utc, 
            RemindersToken.email == email))
        for token in qry.fetch():
            token.key.delete()

    @classmethod
    def createAndSendToken(cls, email, reminders_url, app_config):
        email = email.lower()
        cls.invalidateTokensForEmail(email)
        dt_now_utc = datetime.utcnow()
        reminders_token = RemindersToken()
        reminders_token.email = email
        reminders_token.created = dt_now_utc
        reminders_token.expires = dt_now_utc + timedelta(days=app_config['REMINDERS_EXPIRE'])
        reminders_token.put()

        body = render_template('reminder-message.txt', 
            reminders_url=reminders_url, config=app_config, 
            email=email, token=reminders_token.key.urlsafe())

        print "SENDING MESSAGE"
        print body

        message = mail.EmailMessage(
            sender=app_config['SUPPORT_EMAIL'],
            subject='Conference reminders link',
            to=email,
            body=body)
        message.send()

