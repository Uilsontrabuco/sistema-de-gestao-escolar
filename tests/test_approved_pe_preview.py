import unittest

from scripts.generate_approved_pe_2027_preview import PCLD_CENTS, build_preview


class ApprovedPEPreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = build_preview()
        cls.by_class = {row["class"]: row for row in cls.preview["classes"]}

    def test_pcld_is_preserved_in_budget_and_neutralized_only_in_pe(self):
        summary = self.preview["summary"]
        self.assertEqual(summary["officialTotalMonthly"], 841486.96)
        self.assertEqual(summary["pcldNeutralizedMonthly"], PCLD_CENTS / 100)
        self.assertEqual(summary["managerialPETotalMonthly"], 799369.16)
        self.assertEqual(
            round(sum(row["pcldNeutralizedMonthly"] for row in self.preview["classes"]), 2),
            PCLD_CENTS / 100,
        )
        self.assertEqual(self.preview["pcld"]["ticketDelinquencyPercent"], 4.5)
        self.assertEqual(self.preview["pcld"]["status"], "RESOLVIDO_NEUTRALIZADO_SOMENTE_NO_PE")

    def test_control_classes_match_approved_scenario_c(self):
        expected = {
            "G2 A": (15420.28, 18, "PARCIAL"),
            "G2 B": (15420.28, 18, "PARCIAL"),
            "G4 B": (19568.37, 23, "DEFINITIVO"),
        }
        for name, (cost, pe, status) in expected.items():
            row = self.by_class[name]
            self.assertEqual(row["totalCostMonthly"], cost)
            self.assertEqual(row["breakEvenStudents"], pe)
            self.assertEqual(row["documentaryStatus"], status)

    def test_nominal_and_double_count_protections_are_preserved(self):
        self.assertEqual(len(self.preview["classes"]), 41)
        self.assertEqual(len(self.preview["teacherProjection2027"]), 50)
        self.assertEqual(sum(row["breakEvenStudents"] for row in self.preview["classes"]), 626)
        self.assertEqual(self.preview["summary"]["doubleCountProtection"]["additionalPersonnelAdded"], 0)
        self.assertEqual(self.by_class["G2 A"]["internDetails"][0]["person"], "Joyce dos Santos Pereira")
        self.assertEqual(self.by_class["G2 B"]["internDetails"][0]["person"], "Larissa Lorrana Miranda de Jesus")
        self.assertTrue(any(item["person"] == "Paula Araujo Dias" and item["amount"] is None
                            for item in self.by_class["G3 B"]["internDetails"]))
        self.assertEqual(self.by_class["G3 B"]["documentaryStatus"], "PARCIAL")
        self.assertEqual(self.by_class["G4 B"]["otherDirectDetails"][0]["person"],
                         "Maria Edna Nivaldina de Barros Santos")


if __name__ == "__main__":
    unittest.main()
