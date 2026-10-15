"""Tunable settings for severity. Everything the justification will quote lives here."""

NOT_HATE = "not_hate"

# severity = confidence x category weight.
# All weights are 1.0 on purpose: nothing yet justifies ranking one hate category
# above another. Change them only with a reason (annotation guideline, supervisor
# decision, or an experiment) and record that reason here.
CATEGORY_WEIGHTS = {
    "racial_ethnic": 1.0,
    "religious": 1.0,
    "political": 1.0,
    "gender_based": 1.0,
    "sexual_orientation": 1.0,
    "hate_unspecified": 1.0,  # the meme component is binary and gives no category
}

# A hate prediction below this confidence counts as zero severity, so classifier
# noise does not pile up in the persistent risk score. Tune on real threads.
CONFIDENCE_FLOOR = 0.5
