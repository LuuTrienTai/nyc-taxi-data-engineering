"""Run Great Expectations on the input schema once per taxi file."""
import os
os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
from src.processing.silver import REQUIRED


def check_taxi_schema(columns):
    import great_expectations as gx
    import pandas as pd

    # The expectation only reads column names. Do not materialize the taxi dataset.
    context = gx.get_context(mode='ephemeral')
    source = context.data_sources.add_pandas('bronze')
    asset = source.add_dataframe_asset('yellow_taxi')
    definition = asset.add_batch_definition_whole_dataframe('schema')
    batch = definition.get_batch(batch_parameters={'dataframe': pd.DataFrame(columns=columns)})
    result = batch.validate(
        gx.expectations.ExpectTableColumnsToMatchSet(column_set=REQUIRED, exact_match=False)
    )
    if not result.success:
        raise ValueError(f'Bronze taxi schema missing columns: {sorted(set(REQUIRED) - set(columns))}')
