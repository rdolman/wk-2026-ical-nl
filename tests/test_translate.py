from scripts.wkical.translate import matchup_title, team_nl

def test_team_translation():
    assert team_nl("Netherlands") == "Nederland"

def test_title():
    assert matchup_title("Netherlands", "Morocco", 3, 1, True) == "WK: 🇳🇱 Nederland - 🇲🇦 Marokko (3–1)"
