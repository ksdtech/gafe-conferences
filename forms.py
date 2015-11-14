from flask_wtf import Form
from wtforms import BooleanField, HiddenField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.fields.html5 import DateField, DateTimeField
from wtforms.compat import iteritems
from wtforms.fields import Field
from wtforms.validators import Optional, Required, ValidationError
from wtforms.widgets import TextInput
 
from datetime import datetime, timedelta, time as dt_time
from dateutil import parser as date_parser
import re

DATEUTIL_TYPEERROR_ISSUE = False

TIMEFIELD_DEFAULT_KWARGS = { 'fuzzy': True } # 'default': datetime(1970, 1, 1) }
TIMEFIELD_DISPLAY_FORMAT = '%I:%M %p'

class StringTimeField(Field):
    """
    StringTimeField represented by a text input, accepts all input text formats
    that `dateutil.parser.parse` will.

    :param parse_kwargs:
        A dictionary of keyword args to pass to the dateutil parse() function.
        See dateutil docs for available keywords.
    :param display_format:
        A format string to pass to strftime() to format dates for display.
    """
    widget = TextInput()

    def __init__(self, label=None, validators=None, parse_kwargs=TIMEFIELD_DEFAULT_KWARGS,
                 display_format=TIMEFIELD_DISPLAY_FORMAT, **kwargs):
        super(StringTimeField, self).__init__(label, validators, **kwargs)
        if parse_kwargs is None:
            parse_kwargs = { 'fuzzy': True }
        self.parse_kwargs = parse_kwargs
        self.display_format = display_format

    def _value(self):
        """
        Canonical string representation of a datetime.time instance. No leading zero,
        12-hour time, AM or PM.
        """
        if self.raw_data:
            return ' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.display_format).lstrip('0') or ''

    def populate_obj(self, obj, name):
        """
        Populates `obj.<name>` with the field's data.
        Assumes that the obj is expecting a string.
        """
        setattr(obj, name, self._value())

    def process_data(self, value):
        """
        Coerce incoming None, datetime.datetime, datetime.time, or string data 
        (usually coming from the form obj) to a datetime.time.
        """
        self.data = value
        if value is not None and type(value) is not dt_time:
            try:
                dt = None
                if type(value) is datetime:
                    dt = value
                else:
                    dt = date_parser.parse(value, **self.parse_kwargs)
                self.data = dt.time()
            except (ValueError, TypeError):
                self.data = None

    def process_formdata(self, valuelist):
        """
        Parse string form data to a datetime.time
        """
        value = None
        if valuelist:
            time_str = ' '.join(valuelist)

            if not time_str:
                self.data = None
                raise ValidationError(self.gettext('Please supply a valid time value'))

            parse_kwargs = self.parse_kwargs.copy()
            if 'default' not in parse_kwargs:
                try:
                    parse_kwargs['default'] = self.default()
                except TypeError:
                    parse_kwargs['default'] = self.default
            try:
                dt = date_parser.parse(time_str, **parse_kwargs)
                self.data = dt.time()
            except ValueError:
                self.data = None
                raise ValidationError(self.gettext('Not a valid time value'))
            except TypeError:
                if not DATEUTIL_TYPEERROR_ISSUE:
                    raise

                # If we're using dateutil 2.2, then consider it a normal
                # ValidationError. Hopefully dateutil fixes this issue soon.
                self.data = None
                raise ValidationError(self.gettext('Not a valid time type'))


# dt_next_week.date()
class UserPrefsForm(Form):
    title = StringField(id='title', label='Title')
    display_name = StringField(id='display_name', label='Display name')
    location = StringField(id='location', label='Location')
    timezone = SelectField(id='timezone', label='Time zone',
        choices=[('America/Los_Angeles', 'Pacific'), 
        ('America/Denver', 'Mountain'), 
        ('America/Chicago', 'Central'), 
        ('America/New_York', 'Eastern')])
    interval = IntegerField(id='interval', label='Interval')
    duration = IntegerField(id='duration', label='Duration')
    first_day_scheduled = DateField(id='first_day_scheduled', label='First day for conferences')
    last_day_scheduled = DateField(id='last_day_scheduled', label='Last day for conferences')
    booking_start_date = DateField(id='booking_start_date', 
        label='Start date for booking access',
        validators=(Optional(),))
    booking_start_time = StringTimeField(id='booking_start_time', 
        label='Start time for booking access', 
        validators=(Optional(),))
    booking_end_date = DateField(id='booking_end_time', 
        label='End date for booking access',
        validators=(Optional(),))
    booking_end_time = StringTimeField(id='booking_end_time', 
        label='End time for booking access',
        validators=(Optional(),))
    minimum_notice_hours = IntegerField(id='minimum_notice_hours',
        label='Minimum booking notice period')
    weekday_start = SelectField(id='weekday_start', 
        label='Starting day of week for booking calendar', 
        coerce=int, choices=[(1, 'Monday'), (0,'Sunday')])

    def validate(self):
        valid = super(UserPrefsForm, self).validate()
        if self.interval.data and self.duration.data and self.duration.data > self.interval.data:
            self.duration.errors.append('Can not exceed interval')
            valid = False
        if self.first_day_scheduled.data and self.last_day_scheduled.data and self.last_day_scheduled.data < self.first_day_scheduled.data:
            self.last_day_scheduled.errors.append('Can not preceed first day for conferences')
            valid = False
        if self.booking_start_time.data and not self.booking_start_date.data:
            self.booking_start_date.errors.append('Required if booking access start time was specified')
            valid = False
        if self.booking_end_time.data and not self.booking_end_date.data:
            self.booking_end_date.errors.append('Required if booking access end time was specified')
            valid = False
        if self.booking_start_date.data and self.booking_end_date.data:
            dt_start = self.booking_start_date.data
            if self.booking_start_time.data:
                dt_start = datetime.combine(dt_start, self.booking_start_time.data)
            dt_end = self.booking_end_date.data
            if self.booking_end_time.data:
                dt_end = datetime.combine(dt_end, self.booking_end_time.data)
            if dt_end < dt_start + timedelta(days=1):
                self.booking_end_date.errors.append('Must specify least 24 hours for booking access')
                valid = False
        return valid


class DayPrefsForm(Form):
    enabled_0 = BooleanField(id='enabled_0', label='Monday enabled')
    day_start_time_0 = StringTimeField(id='day_start_time_0', label='Monday day start')
    lunch_start_time_0 = StringTimeField(id='lunch_start_time_0', label='Monday lunch start',
        validators=(Optional(),))
    lunch_end_time_0 = StringTimeField(id='lunch_end_time_0', label='Monday lunch end',
        validators=(Optional(),))
    day_end_time_0 = StringTimeField(id='day_end_time_0', label='Monday day end')

    enabled_1 = BooleanField(id='enabled_1', label='Tuesday enabled')
    day_start_time_1 = StringTimeField(id='day_start_time_1', label='Tuesday day start')
    lunch_start_time_1 = StringTimeField(id='lunch_start_time_1', label='Tuesday lunch start',
        validators=(Optional(),))
    lunch_end_time_1 = StringTimeField(id='lunch_end_time_1', label='Tuesday lunch end',
        validators=(Optional(),))
    day_end_time_1 = StringTimeField(id='day_end_time_1', label='Tuesday day end')

    enabled_2 = BooleanField(id='enabled_2', label='Wednesday enabled')
    day_start_time_2 = StringTimeField(id='day_start_time_2', label='Wednesday day start')
    lunch_start_time_2 = StringTimeField(id='lunch_start_time_2', label='Wednesday lunch start',
        validators=(Optional(),))
    lunch_end_time_2 = StringTimeField(id='lunch_end_time_2', label='Wednesday lunch end',
        validators=(Optional(),))
    day_end_time_2 = StringTimeField(id='day_end_time_2', label='Wednesday day end')

    enabled_3 = BooleanField(id='enabled_3', label='Thursday enabled')
    day_start_time_3 = StringTimeField(id='day_start_time_3', label='Thursday day start')
    lunch_start_time_3 = StringTimeField(id='lunch_start_time_3', label='Thursday lunch start',
        validators=(Optional(),))
    lunch_end_time_3 = StringTimeField(id='lunch_end_time_3', label='Thursday lunch end',
        validators=(Optional(),))
    day_end_time_3 = StringTimeField(id='day_end_time_3', label='Thursday day end')

    enabled_4 = BooleanField(id='enabled_4', label='Friday enabled')
    day_start_time_4 = StringTimeField(id='day_start_time_4', label='Friday day start')
    lunch_start_time_4 = StringTimeField(id='lunch_start_time_4', label='Friday lunch start',
        validators=(Optional(),))
    lunch_end_time_4 = StringTimeField(id='lunch_end_time_4', label='Friday lunch end',
        validators=(Optional(),))
    day_end_time_4 = StringTimeField(id='day_end_time_4', label='Friday day end')

    enabled_5 = BooleanField(id='enabled_5', label='Saturday enabled')
    day_start_time_5 = StringTimeField(id='day_start_time_5', label='Saturday day start')
    lunch_start_time_5 = StringTimeField(id='lunch_start_time_5', label='Saturday lunch start',
        validators=(Optional(),))
    lunch_end_time_5 = StringTimeField(id='lunch_end_time_5', label='Saturday lunch end',
        validators=(Optional(),))
    day_end_time_5 = StringTimeField(id='day_end_time_5', label='Saturday day end')

    enabled_6 = BooleanField(id='enabled_6', label='Sunday enabled')
    day_start_time_6 = StringTimeField(id='day_start_time_6', label='Sunday day start')
    lunch_start_time_6 = StringTimeField(id='lunch_start_time_6', label='Sunday lunch start',
        validators=(Optional(),))
    lunch_end_time_6 = StringTimeField(id='lunch_end_time_6', label='Sunday lunch end',
        validators=(Optional(),))
    day_end_time_6 = StringTimeField(id='day_end_time_6', label='Sunday day end')

    def populate_obj(self, obj):
        """
        Overrides wtforms.form.py BaseForm.process.
        Since we're going to populate to repeating fields in the object,
        We have to play games with the field names.
        """
        for name, field in iteritems(self._fields):
            m = re.search(r'^(.+)_([0-6])$', name)
            if m:
                attr_name = m.group(1)
                index = int(m.group(2))
                day_prefs_obj = obj.days[index]
                field.populate_obj(day_prefs_obj, attr_name)

    def process(self, formdata=None, obj=None, data=None, **kwargs):
        """
        Overrides wtforms.form.py BaseForm.process.
        Since we're going to load form fields from repeating fields in the object,
        We have to play games with the field names.
        """
        formdata = self.meta.wrap_formdata(self, formdata)

        if data is not None:
            # XXX we want to eventually process 'data' as a new entity.
            #     Temporarily, this can simply be merged with kwargs.
            kwargs = dict(data, **kwargs)

        for name, field, in iteritems(self._fields):
            processed_from_obj = False
            if obj is not None:
                m = re.search(r'^(.+)_([0-6])$', name)
                if m:
                    attr_name = m.group(1)
                    index = int(m.group(2))
                    day_prefs_obj = obj.days[index]
                    if hasattr(day_prefs_obj, attr_name):
                        field.process(formdata, getattr(day_prefs_obj, attr_name))
                        processed_from_obj = True
            if not processed_from_obj:
                if name in kwargs:
                    field.process(formdata, kwargs[name])
                else:
                    field.process(formdata) 

    def validate(self):
        valid = super(DayPrefsForm, self).validate()
        for i in range(7):
            pairs = [('day_start_time', 'day_end_time'), ('lunch_start_time', 'lunch_end_time'),
                ('day_start_time', 'lunch_start_time'), ('lunch_end_time', 'day_end_time')]
            for j, pair in enumerate(pairs):
                f1_name = '%s_%d' % (pair[0], i)
                f2_name = '%s_%d' % (pair[1], i)
                f1 = self[f1_name]
                f2 = self[f2_name]

                if f1.data and f2.data and f2.data < f1.data:
                    f2.errors.append('Can not preceed %s' % f1.label.text)
                    valid = False
                if j == 1:
                    if f2.data and not f1.data:
                        f1.errors.append('Required if %s specified' % f2.label.text)
                        valid = False
                    if f1.data and not f2.data:
                        f2.errors.append('Required if %s specified' % f1.label.text)
                        valid = False
        return valid

class BookingForm(Form):
    start_time = HiddenField()
    end_time = HiddenField()
    timezone = HiddenField()
    email = StringField(validators=(Required(),))
    phone = StringField(validators=(Required(),))
    first_name = StringField(validators=(Required(),))
    last_name = StringField(validators=(Required(),))
    notes = TextAreaField(validators=(Optional(),))
