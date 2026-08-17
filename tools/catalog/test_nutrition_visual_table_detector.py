import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from nutrition_visual_table_detector import detect_visual_table_regions


class VisualTableDetectorTest(unittest.TestCase):
    def test_detects_synthetic_table_without_text_recognition(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'table.png'; out=Path(td)/'out'
            image=np.full((1000,1400,3),255,dtype=np.uint8)
            x1,y1,x2,y2=260,210,1120,810
            cv2.rectangle(image,(x1,y1),(x2,y2),(0,0,0),5)
            for y in range(y1+90,y2,85):
                cv2.line(image,(x1,y),(x2,y),(0,0,0),4)
            for x in (x1+520,x1+690):
                cv2.line(image,(x,y1),(x,y2),(0,0,0),3)
            # Simulate dense text strokes without meaningful OCR words.
            for row in range(6):
                yy=y1+50+row*85
                for col in range(8):
                    xx=x1+35+col*55
                    cv2.rectangle(image,(xx,yy),(xx+28,yy+12),(0,0,0),-1)
            cv2.imwrite(str(src),image)
            regions=detect_visual_table_regions(src,out)
            self.assertTrue(regions)
            r=regions[0]
            self.assertGreaterEqual(r.horizontal_lines,4)
            self.assertGreater(r.score,.44)
            self.assertTrue(r.path.exists())

    def test_plain_text_like_strokes_do_not_form_table(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'plain.png'; out=Path(td)/'out'
            image=np.full((800,1200,3),255,dtype=np.uint8)
            for row in range(12):
                y=80+row*50
                for col in range(10):
                    x=80+col*70
                    cv2.rectangle(image,(x,y),(x+30,y+10),(0,0,0),-1)
            cv2.imwrite(str(src),image)
            self.assertEqual(detect_visual_table_regions(src,out),[])


if __name__=='__main__':
    unittest.main()
