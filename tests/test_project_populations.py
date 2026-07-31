import pandas as pd

from tootuft2count.populations import evaluate_population
from tootuft2count.project import Project, SampleState


def test_project_round_trip(tmp_path):
    project = Project(str(tmp_path), samples=[SampleState("one", [])])
    path = project.save()
    loaded = Project.load(path)
    assert loaded.samples[0].name == "one"
    assert not path.with_suffix(".json.tmp").exists()


def test_boolean_population_rules():
    data = pd.DataFrame({"DAPI_sum": [5, 5, 0], "A_sum": [5, 0, 5], "B_sum": [0, 5, 5]})
    selected = evaluate_population(data, "DAPI+ AND (A+ OR B+)", {"DAPI": 1, "A": 1, "B": 1})
    assert selected.tolist() == [True, True, False]
    negative = evaluate_population(data, "DAPI+ AND NOT A+", {"DAPI": 1, "A": 1})
    assert negative.tolist() == [False, True, False]

