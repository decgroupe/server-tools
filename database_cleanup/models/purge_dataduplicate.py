# Copyright 2014-2016 Therp BV <http://therp.nl>
# Copyright 2021 Camptocamp <https://camptocamp.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..identifier_adapter import IdentifierAdapter


class CleanupPurgeLineDataDuplicate(models.TransientModel):
    _inherit = "cleanup.purge.line"
    _name = "cleanup.purge.line.dataduplicate"
    _description = "Cleanup Purge Line Data Duplicate"

    name = fields.Char()
    model = fields.Char(string="Model Name", required=True)
    # module = fields.Char(default='', required=True)
    res_id = fields.Integer(string="Record ID")
    count = fields.Integer(string="Count")
    data_ids = fields.Many2many(
        string="Records",
        comodel_name="ir.model.data",
        relation="cleanup_purge_line_dataduplicate_rel",
    )
    wizard_id = fields.Many2one(
        "cleanup.purge.wizard.dataduplicate", "Purge Wizard", readonly=True
    )

    def purge(self):
        """Unlink data entries upon manual confirmation."""
        if self:
            objs = self
        else:
            objs = self.env["cleanup.purge.line.dataduplicate"].browse(
                self._context.get("active_ids")
            )
        to_unlink = objs.filtered(lambda x: not x.purged and x.data_ids)
        self.logger.info("Purging data duplicate entries: %s", to_unlink.mapped("name"))
        to_unlink.mapped("data_ids").unlink()
        return to_unlink.write({"purged": True})


class CleanupPurgeWizardDataDuplicate(models.TransientModel):
    _inherit = "cleanup.purge.wizard"
    _name = "cleanup.purge.wizard.dataduplicate"
    _description = "Purge data duplicates"

    @api.model
    def find(self):
        """Collect all rows from ir_model_data that refer
        to a nonexisting model, or to a nonexisting
        row in the model's table."""
        res = []
        data_ids = []
        unknown_models = []
        self.env.cr.execute(
            """
            SELECT
                model, res_id, COUNT(*)
            FROM
                ir_model_data
            GROUP BY
                model, res_id
            HAVING
                COUNT(*) > 1
            """
        )
        for model_name, res_id, count in self.env.cr.fetchall():
            if not model_name:
                continue
            elif model_name in (
                "ir.model",
                "ir.model.fields",
                "ir.model.fields.selection",
                "res.lang",
            ):
                continue
            elif model_name not in self.env:
                unknown_models.append(model_name)
                continue
            domain = [
                ("model", "=", model_name),
                ("res_id", "=", res_id),
            ]
            data_ids = self.env["ir.model.data"].search(domain)
            res.append(
                (
                    0,
                    0,
                    {
                        "name": set(data_ids.mapped("display_name")),
                        "model": model_name,
                        "res_id": res_id,
                        "count": count,
                        "data_ids": [(6, 0, data_ids.ids)],
                        # "name": "%s.%s, object of type %s"
                        # % (data.module, data.name, data.model),
                    },
                )
            )
            # lst.append("%s.%s" % (m.module, m.name))
        if not res:
            raise UserError(_("No duplicated data entries found"))
        return res

    purge_line_ids = fields.One2many(
        "cleanup.purge.line.dataduplicate", "wizard_id", "Duplicates data to purge"
    )
