odoo.define('gtm_appointments.appointment_form', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var websiteCalendarForm = publicWidget.registry.websiteCalendarForm;


websiteCalendarForm.include({
    events: _.extend({}, websiteCalendarForm.prototype.events, {
        'submit .appointment_submit_form': '_on_submit_appointment'
    }),

    _on_submit_appointment: function (ev) {
        if (window.dataLayer) {
            var appointment_datetime = $(ev.target).find('input[name="datetime_str"]').first().val();
            var [date, time] = appointment_datetime.split(' ');
            var branch = ev.target.action.match(/(calendar\/)(.*?)(-[0-9]+\/submit)/)[2];

            window.dataLayer.push({
                'event': 'cita_registrada',
                'dia_cita': date,
                'hora_cita': time,
                'sucursal': branch
            });
        }
    }
});

});
