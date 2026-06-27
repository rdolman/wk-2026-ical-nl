from scripts.wkical.translate import team_nl, matchup_title

def test_team_translation():
    assert team_nl("Netherlands") == "Nederland"
    assert team_nl("Morocco") == "Marokko"

def test_matchup_completed():
    assert "Nederland 3–1 Marokko" in matchup_title("Netherlands", "Morocco", 3, 1, True)
