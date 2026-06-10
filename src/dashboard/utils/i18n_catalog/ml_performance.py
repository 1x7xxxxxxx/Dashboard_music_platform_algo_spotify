"""EN catalog for the ml_performance view."""

EN = {
    "ml_performance.no_artifacts": "No PNG artifact found for this run (`mlruns/{exp_id}/{run_id}/`).",
    "ml_performance.predictions_error": "Error while fetching predictions: {err}",
    "ml_performance.no_predictions": "No prediction in database. Run the `ml_scoring_daily` DAG to generate scores.",
    "ml_performance.predictions_count": "**{count} prediction(s) found**",
    "ml_performance.songs_all": "(all)",
    "ml_performance.filter_by_song": "Filter by song",
    "ml_performance.scorecard_caption": "Offline evaluation metrics (test set). Source: `machine_learning/` analysis.",
    "ml_performance.scorecard_unavailable": "{algo}: classification scorecard not available yet.",
    "ml_performance.access_denied": "⛔ Access restricted to administrators.",
    "ml_performance.title": "🤖 ML Model Performance",
    "ml_performance.intro": "MLflow artifacts of active models + tracking of scores in the database.",
    "ml_performance.tab_scorecard": "📋 Classification scorecard",
    "ml_performance.tab_predictions": "🎯 Predictions in DB",
    "ml_performance.mlflow_experiment": "MLflow experiment #{exp_id} — run `{run_id}…`",
}
