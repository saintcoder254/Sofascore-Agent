from titan_incident_audit import TitanIncidentAudit
def test_incident_audit_flags_overconfidence():
    r=TitanIncidentAudit().audit_prediction({"prediction_id":"x","fixture_id":"f","market":"TOTAL_POINTS","selection":"UNDER 177.5","predicted_probability":0.75,"outcome":0})
    assert r["overconfidence"] is True
