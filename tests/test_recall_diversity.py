from membrain.recall_diversity import diversify


def row(identifier, text, *, world="real_world"):
    return {"document": {"memory_id": identifier, "revision": 1, "statement": text, "world": world}}


def test_repeated_numeric_templates_reorder_without_removing_or_mutating_sources():
    records = [row(str(index), f"I filed invoice {index} in the blue cabinet beside the office door.")
               for index in range(20)]
    unique = row("unique", "The spare umbrella is stored in the entrance cupboard.")
    result = diversify([*records, unique])

    assert result[:3] == [*records[:2], unique]
    assert result[3:] == records[2:]
    assert {id(value) for value in result} == {id(value) for value in [*records, unique]}


def test_negation_is_not_deferred_as_another_copy_of_a_positive_report():
    template = ("During my review of the quarterly delivery records for shipment NUMBER at the riverside office, "
                "I confirmed that the customer received the signed paperwork before the afternoon meeting.")
    first = row("first", template.replace("NUMBER", "100"))
    second = row("second", template.replace("NUMBER", "101"))
    denied = row("denied", template.replace("NUMBER", "102").replace("customer received", "customer never received"))
    different = row("different", "The spare umbrella is stored in the entrance cupboard.")

    assert diversify([first, second, denied, different]) == [first, second, denied, different]


def test_different_names_and_worlds_are_not_combined():
    records = [row(str(index), f"I gave Alex the sealed package for shipment {index} before the afternoon meeting.")
               for index in range(2)]
    person = row("other-person", "I gave Alec the sealed package for shipment 9 before the afternoon meeting.")
    dream = row("dream", records[0]["document"]["statement"], world="dream")
    different = row("different", "The spare umbrella is stored in the entrance cupboard.")

    assert diversify([*records, person, dream, different]) == [*records, person, dream, different]
