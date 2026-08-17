import tempfile
import unittest
from pathlib import Path

from label_text_extractor import extract_with_tesseract
from nutrition_label_reader import read_nutrition_label


def tsv_for(lines):
    header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'
    rows=[header]
    line_no=1
    for line in lines:
        word_no=1
        for word in line.split():
            rows.append(f'5\t1\t1\t1\t{line_no}\t{word_no}\t0\t0\t10\t10\t95\t{word}')
            word_no+=1
        line_no+=1
    return '\n'.join(rows)


class LabelTextExtractorTest(unittest.TestCase):
    def test_tesseract_tsv_can_feed_declared_reader(self):
        lines=[
            'INFORMACION NUTRICIONAL por 100 ml',
            'Valor energetico 256 kJ 61 kcal',
            'Grasas 0,9 g',
            'Hidratos de carbono 10 g',
            'Proteinas 3,1 g',
            'Sal 0,14 g',
        ]
        def runner(args, path):
            return tsv_for(lines), ''
        with tempfile.TemporaryDirectory() as td:
            image=Path(td)/'label.jpg'; image.write_bytes(b'fixture')
            extraction=extract_with_tesseract(image,runner=runner)
        self.assertGreaterEqual(extraction.confidence,.94)
        parsed=read_nutrition_label(extraction.text, extraction_confidence=extraction.confidence)
        self.assertTrue(parsed.declared_usable, parsed)
        self.assertEqual(parsed.basis,'100ml')
        self.assertEqual(parsed.nutrition['calories'],61)
        self.assertEqual(parsed.nutrition['fat_g'],.9)
        self.assertEqual(parsed.nutrition['carbohydrate_g'],10)
        self.assertEqual(parsed.nutrition['protein_g'],3.1)

    def test_low_confidence_never_becomes_declared(self):
        def runner(args,path):
            return tsv_for(['INFORMACION NUTRICIONAL por 100 g','Valor energetico 432 kcal','Grasas 9,4 g','Hidratos de carbono 78 g','Proteinas 7,6 g']).replace('\t95\t','\t55\t'),''
        with tempfile.TemporaryDirectory() as td:
            image=Path(td)/'label.jpg'; image.write_bytes(b'fixture')
            extraction=extract_with_tesseract(image,runner=runner)
        parsed=read_nutrition_label(extraction.text, extraction_confidence=extraction.confidence)
        self.assertFalse(parsed.declared_usable)
        self.assertEqual(parsed.status,'REVIEW')

if __name__=='__main__': unittest.main()
