import json
import unittest
from pathlib import Path

from src.features.tickets.view.TicketFormModal import TicketFormModal


class TicketFormModalTests(unittest.IsolatedAsyncioTestCase):
    async def test_team_registration_optional_fields(self):
        config = json.loads((Path(__file__).parents[1] / "config/tickets.json").read_text(encoding="utf-8"))
        category = config["ticketCategories"][0]
        modal = TicketFormModal(category["name"], category, None)

        self.assertEqual([field.required for field in modal.children], [True, False, False])
        self.assertEqual([field.min_length for field in modal.children], [1, 0, 0])
        self.assertEqual(
            [field.to_component_dict().get("required") for field in modal.children[1:]],
            [False, False],
        )


if __name__ == "__main__":
    unittest.main()
