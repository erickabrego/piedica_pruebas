from odoo import api, fields, models
from odoo.exceptions import ValidationError
import datetime
import requests

class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def create(self, vals_list):
        res = super(CalendarEvent, self).create(vals_list)
        message = f"Su cita ha sido agendada con la fecha {res.start_date}"
        res.send_irina_message(message=message)
        return res


    def send_irina_message(self, message=None):
        for rec in self:
            url = f"https://app.irina.chat/api/v1/messages/send_template"
            partners = rec.partner_ids.filtered(lambda line: line.x_studio_es_paciente)
            for partner in partners:
                if partner.mobile:
                    message_data = {
                        "to": f"{partner.mobile}",
                        "number_id": "222222222222",
                        "template_name": "notificación_cita",
                        "template_language": "es_mx",
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {
                                        "type": "text",
                                        "text": f"{message}"
                                    }
                                ]
                            }
                        ],
                        "contact": {
                            "name": f"{partner.name}",
                            "last_name": ""
                        }
                    }
                    response = requests.post(url, data=message_data)
                    print(response)
                else:
                    raise ValidationError("El paciente debe de tener un número móvil para comunicarse con él mediante whatsapp.")

    def notify_irina_before(self, events):
        for event in events:
            event.send_irina_message(f"Recuerda que tu cita es el {event.start_date}, lo esperamos.")