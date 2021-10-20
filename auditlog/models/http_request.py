# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2.extensions import AsIs
from xmlrpc.client import loads

from odoo import models, fields, api
from odoo.http import request


class AuditlogHTTPRequest(models.Model):
    _name = 'auditlog.http.request'
    _description = "Auditlog - HTTP request log"
    _order = "create_date DESC"

    display_name = fields.Char(
        "Name", compute="_compute_display_name", store=True)
    name = fields.Char("Path")
    root_url = fields.Char("Root URL")
    user_id = fields.Many2one(
        'res.users', string="User")
    http_session_id = fields.Many2one(
        'auditlog.http.session', string="Session")
    user_context = fields.Char("Context")
    log_ids = fields.One2many(
        'auditlog.log', 'http_request_id', string="Logs")

    @api.depends('create_date', 'name')
    def _compute_display_name(self):
        for httprequest in self:
            create_date = fields.Datetime.from_string(httprequest.create_date)
            tz_create_date = fields.Datetime.context_timestamp(
                httprequest, create_date)
            httprequest.display_name = "%s (%s)" % (
                httprequest.name or '?',
                fields.Datetime.to_string(tz_create_date))

    @api.multi
    def name_get(self):
        return [(request.id, request.display_name) for request in self]

    @api.model
    def current_http_request(self):
        """Create a log corresponding to the current HTTP request, and returns
        its ID. This method can be called several times during the
        HTTP query/response cycle, it will only log the request on the
        first call.
        If no HTTP request is available, returns `False`.
        """
        if not request:
            return False
        http_session_model = self.env['auditlog.http.session']
        httprequest = request.httprequest
        if httprequest:
            if hasattr(httprequest, 'auditlog_http_request_id'):
                # Verify existence. Could have been rolled back after a
                # concurrency error
                self.env.cr.execute(
                    "SELECT id FROM %s WHERE id = %s", (
                        AsIs(self._table),
                        httprequest.auditlog_http_request_id))
                if self.env.cr.fetchone():
                    return httprequest.auditlog_http_request_id
            name = httprequest.path
            if httprequest.path.startswith('/xmlrpc/'):
                data = httprequest.get_data()
                params, method = loads(data)
                (db, user_id, passwd ) = params[0], int(params[1]), params[2]
                user_context = False
                params = params[3:]
                if method in ['execute', 'execute_kw']:
                    model, model_method, model_method_args = params[0], params[1], params[2]
                    name = "%s > %s.%s()" % (name, model, model_method)
                    if method == 'execute_kw':
                        model_method_kwargs = params[3]
                        user_context = model_method_kwargs.get('context', False)
                    else:
                        model_method_kwargs = {}
            else:
                user_id = request.uid
                user_context = request.context
            vals = {
                'name': name,
                'root_url': httprequest.url_root,
                'user_id': user_id,
                'http_session_id': http_session_model.current_http_session(),
                'user_context': user_context,
            }
            httprequest.auditlog_http_request_id = self.create(vals).id
            return httprequest.auditlog_http_request_id
        return False
