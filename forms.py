from flask_wtf import Form
from wtforms import BooleanField, DateField, DateTimeField, HiddenField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.compat import iteritems
from wtforms.fields import Field
from wtforms.validators import Optional, Required, ValidationError
from wtforms.widgets import TextInput
 
from dateutil import parser as date_parser
import re

DATEUTIL_TYPEERROR_ISSUE = False

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

    def __init__(self, label=None, validators=None, parse_kwargs=None,
                 display_format='%I:%M %p', **kwargs):
        super(StringTimeField, self).__init__(label, validators, **kwargs)
        if parse_kwargs is None:
            parse_kwargs = { 'fuzzy': True }
        self.parse_kwargs = parse_kwargs
        self.display_format = display_format

    def _value(self):
        if self.raw_data:
            return ' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.display_format).lstrip('0') or ''

    def process_data(self, date_str):
        if not date_str:
            self.data = None
            raise ValidationError(self.gettext('Please input a date/time value'))

        parse_kwargs = self.parse_kwargs.copy()
        if 'default' not in parse_kwargs:
            try:
                parse_kwargs['default'] = self.default()
            except TypeError:
                parse_kwargs['default'] = self.default
        try:
            self.data = date_parser.parse(date_str, **parse_kwargs)
        except ValueError:
            self.data = None
            raise ValidationError(self.gettext('Invalid date/time input'))
        except TypeError:
            if not DATEUTIL_TYPEERROR_ISSUE:
                raise

            # If we're using dateutil 2.2, then consider it a normal
            # ValidationError. Hopefully dateutil fixes this issue soon.
            self.data = None
            raise ValidationError(self.gettext('Invalid date/time input'))

    def process_formdata(self, valuelist):
        date_str = None
        if valuelist:
            date_str = ' '.join(valuelist)
        self.process_data(date_str)


class UserPrefsForm(Form):
    title = StringField('title')
    display_name = StringField('display_name')
    location = StringField('location')
    timezone = StringField('timezone')
    interval = IntegerField('interval')
    duration = IntegerField('duration')
    first_day_scheduled = DateField('first_day_scheduled')
    last_day_scheduled = DateField('last_day_scheduled')
    booking_start_date = DateField('booking_start_date', validators=(Optional(),))
    booking_start_time = StringTimeField('booking_start_time', validators=(Optional(),))
    booking_end_date = DateField('booking_end_time', validators=(Optional(),))
    booking_end_time = StringTimeField('booking_end_time', validators=(Optional(),))
    minimum_notice_hours = IntegerField('minimum_notice_hours')
    weekday_start = SelectField('weekday_start', choices=[(1, 'Monday'), (0,'Sunday')],  coerce=int)


class DayPrefsForm(Form):
    enabled_0 = BooleanField()
    day_start_time_0 = StringTimeField(validators=(Required(),))
    lunch_start_time_0 = StringTimeField(validators=(Required(),))
    lunch_end_time_0 = StringTimeField(validators=(Required(),))
    day_end_time_0 = StringTimeField(validators=(Required(),))
    enabled_1 = BooleanField()
    day_start_time_1 = StringTimeField(validators=(Required(),))
    lunch_start_time_1 = StringTimeField(validators=(Required(),))
    lunch_end_time_1 = StringTimeField(validators=(Required(),))
    day_end_time_1 = StringTimeField(validators=(Required(),))
    enabled_2 = BooleanField()
    day_start_time_2 = StringTimeField(validators=(Required(),))
    lunch_start_time_2 = StringTimeField(validators=(Required(),))
    lunch_end_time_2 = StringTimeField(validators=(Required(),))
    day_end_time_2 = StringTimeField(validators=(Required(),))
    enabled_3 = BooleanField()
    day_start_time_3 = StringTimeField(validators=(Required(),))
    lunch_start_time_3 = StringTimeField(validators=(Required(),))
    lunch_end_time_3 = StringTimeField(validators=(Required(),))
    day_end_time_3 = StringTimeField(validators=(Required(),))
    enabled_4 = BooleanField()
    day_start_time_4 = StringTimeField(validators=(Required(),))
    lunch_start_time_4 = StringTimeField(validators=(Required(),))
    lunch_end_time_4 = StringTimeField(validators=(Required(),))
    day_end_time_4 = StringTimeField(validators=(Required(),))
    enabled_5 = BooleanField()
    day_start_time_5 = StringTimeField(validators=(Required(),))
    lunch_start_time_5 = StringTimeField(validators=(Required(),))
    lunch_end_time_5 = StringTimeField(validators=(Required(),))
    day_end_time_5 = StringTimeField(validators=(Required(),))
    enabled_6 = BooleanField()
    day_start_time_6 = StringTimeField(validators=(Required(),))
    lunch_start_time_6 = StringTimeField(validators=(Required(),))
    lunch_end_time_6 = StringTimeField(validators=(Required(),))
    day_end_time_6 = StringTimeField(validators=(Required(),))

    def populate_obj(self, obj):
        """
        Populates the attributes of the passed `obj` with data from the form's
        fields.

        :note: This is a destructive operation; Any attribute with the same name
               as a field will be overridden. Use with caution.
        """
        for name, field in iteritems(self._fields):
            m = re.search(r'^(.+)_([0-6])$', name)
            if m:
                attr_name = m.group(1)
                index = int(m.group(2))
                day_prefs_obj = obj.days[index]
                field.populate_obj(day_prefs_obj, name)

    def process(self, formdata=None, obj=None, data=None, **kwargs):
        """
        Take form, object data, and keyword arg input and have the fields
        process them.

        :param formdata:
            Used to pass data coming from the enduser, usually `request.POST` or
            equivalent.
        :param obj:
            If `formdata` is empty or not provided, this object is checked for
            attributes matching form field names, which will be used for field
            values.
        :param data:
            If provided, must be a dictionary of data. This is only used if
            `formdata` is empty or not provided and `obj` does not contain
            an attribute named the same as the field.
        :param `**kwargs`:
            If `formdata` is empty or not provided and `obj` does not contain
            an attribute named the same as a field, form will assign the value
            of a matching keyword argument to the field, if one exists.
        """
        formdata = self.meta.wrap_formdata(self, formdata)

        if data is not None:
            # XXX we want to eventually process 'data' as a new entity.
            #     Temporarily, this can simply be merged with kwargs.
            kwargs = dict(data, **kwargs)

        for name, field, in iteritems(self._fields):
            if obj is not None:
                m = re.search(r'^(.+)_([0-6])$', name)
                if m:
                    attr_name = m.group(1)
                    index = int(m.group(2))
                    day_prefs_obj = obj.days[index]
                    if hasattr(day_prefs_obj, attr_name):
                        field.process(formdata, getattr(day_prefs_obj, attr_name))
            elif name in kwargs:
                field.process(formdata, kwargs[name])
            else:
                field.process(formdata) 


class BookingForm(Form):
    start_time = HiddenField()
    end_time = HiddenField()
    timezone = HiddenField()
    email = StringField(validators=(Required(),))
    phone = StringField(validators=(Required(),))
    first_name = StringField(validators=(Required(),))
    last_name = StringField(validators=(Required(),))
    notes = TextAreaField(validators=(Optional(),))
