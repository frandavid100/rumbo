from aesan_2022_match_probe import _name_similarity, _same_brand, norm, digits


def test_normalization_and_digits():
    assert norm("Jamón cocido, extra") == "jamon cocido extra"
    assert digits("8480000-123456") == "8480000123456"


def test_brand_matching_is_conservative():
    assert _same_brand("Hacendado", "HACENDADO")
    assert _same_brand("Hacendado", "Hacendado / Mercadona")
    assert not _same_brand("Hacendado", "Campofrío")
    assert not _same_brand(None, "Hacendado")


def test_name_similarity_prefers_same_product_wording():
    same = _name_similarity("Yogur griego natural Hacendado", "Yogur griego natural")
    different = _name_similarity("Yogur griego natural Hacendado", "Galletas María tostadas")
    assert same > 0.78
    assert different < 0.5
