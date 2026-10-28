import unittest

from clock_tools import clock_reference_rows, convert_clock_time


class ClockToolsTests(unittest.TestCase):
    def test_conversion_in_both_directions(self):
        cases = {
            "12:00 AM": ("00:00", "12:00 AM"),
            "12 PM": ("12:00", "12:00 PM"),
            "2:30 pm": ("14:30", "2:30 PM"),
            "14:30": ("14:30", "2:30 PM"),
            "1430": ("14:30", "2:30 PM"),
            "2:30": ("02:30", "2:30 AM"),
            "23:59": ("23:59", "11:59 PM"),
            "00:00": ("00:00", "12:00 AM"),
            "0": ("00:00", "12:00 AM"),
            "14": ("14:00", "2:00 PM"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(convert_clock_time(text), expected)

    def test_invalid_and_ambiguous_formats_are_rejected(self):
        for text in ("", "24:00", "12:60 PM", "13 PM", "2:3 PM", "230",
                     "2 PM UTC", "noon", None):
            with self.subTest(text=text), self.assertRaises(ValueError):
                convert_clock_time(text)

    def test_reference_covers_each_hour_once(self):
        rows = clock_reference_rows()
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0], ("00:00", "12:00 AM", "12:00", "12:00 PM"))
        self.assertEqual(rows[-1], ("11:00", "11:00 AM", "23:00", "11:00 PM"))
        self.assertEqual({value for row in rows for value in (row[0], row[2])},
                         {f"{hour:02d}:00" for hour in range(24)})


if __name__ == "__main__":
    unittest.main()
