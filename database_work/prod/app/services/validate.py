from __future__ import annotations
import pandas as pd


class TestValidation:

    def __init__(self, df: pd.DataFrame):
        self.expected_schema = [
            "uuid",
            "name",
            "phone",
            "job",
            "vin",
            "city",
            "governance_status",
            "created_at",
            ]

        self.ingested_df = df

    def validate(self) -> bool:
        return all(column in self.ingested_df.columns for column in self.expected_schema)

    def get_missing_columns(self) -> list[str]:
        return [column for column in self.expected_schema if column not in self.ingested_df.columns]