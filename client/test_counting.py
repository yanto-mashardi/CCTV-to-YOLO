import unittest
from counting import Counter
class TestCounter(unittest.TestCase):
    def test_inbound_and_duplicate(self):
        c=Counter([[.1,.5],[.9,.5]],"negative_to_positive")
        self.assertFalse(c.update(1,(.5,.4),0))
        self.assertTrue(c.update(1,(.5,.6),1))
        self.assertFalse(c.update(1,(.5,.4),2))
        self.assertFalse(c.update(1,(.5,.6),3))
    def test_outside_line(self):
        c=Counter([[.1,.5],[.9,.5]],"negative_to_positive")
        c.update(1,(.99,.4),0)
        self.assertFalse(c.update(1,(.99,.6),1))
    def test_gap(self):
        c=Counter([[.1,.5],[.9,.5]],"negative_to_positive")
        c.update(1,(.5,.4),0)
        self.assertFalse(c.update(1,(.5,.6),9))
if __name__=="__main__": unittest.main()
