import unittest

from src.defects import count_severities, defect_ids, parse_rikked, split_rikked_entries


class DefectParsingTest(unittest.TestCase):
    def test_parse_semicolon_delimited_defects(self):
        parsed = parse_rikked("VO:100101460;OV:100103882;EOV:100104012")

        self.assertEqual(
            parsed,
            [
                ("VO", 100101460),
                ("OV", 100103882),
                ("EOV", 100104012),
            ],
        )

    def test_parse_comma_and_newline_delimited_defects(self):
        parsed = parse_rikked("VO:1, OV:2\nEOV:3")

        self.assertEqual(parsed, [("VO", 1), ("OV", 2), ("EOV", 3)])

    def test_ignore_invalid_entries(self):
        parsed = parse_rikked("VO:1;BAD:2;OV:not-number;EOV:3")

        self.assertEqual(parsed, [("VO", 1), ("EOV", 3)])

    def test_empty_values(self):
        self.assertEqual(parse_rikked(""), [])
        self.assertEqual(parse_rikked(None), [])

    def test_counts_are_exact_by_severity(self):
        parsed = parse_rikked("OV:1;EOV:2;VO:3")
        counts = count_severities(parsed)

        self.assertEqual(counts["VO"], 1)
        self.assertEqual(counts["OV"], 1)
        self.assertEqual(counts["EOV"], 1)

    def test_defect_ids(self):
        self.assertEqual(defect_ids(parse_rikked("VO:10;OV:20")), [10, 20])

    def test_splits_raw_entries(self):
        self.assertEqual(
            split_rikked_entries(" VO:1 ;\nOV:2,,EOV:3 "),
            ["VO:1", "OV:2", "EOV:3"],
        )


if __name__ == "__main__":
    unittest.main()
