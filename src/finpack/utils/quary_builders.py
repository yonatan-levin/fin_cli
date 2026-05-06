from __future__ import annotations

from typing import Iterable, Tuple

from ..models.stock_screening.params.const import BASE_URL
from ..models.stock_screening.params.descriptive_params import Descriptive_Params
from ..models.stock_screening.params.fundamental_params import Fundamental_Params
from ..models.stock_screening.params.technical_params import Technical_Params


def build_stock_screener_query(filters_tuple: Iterable[Tuple[str, str]], v: int = 111, ft: int = 2) -> str:
    """Build a Finviz screener query URL from filter key/value pairs.

    filters_tuple: iterable of (filter_key, selected_value_key)
    """

    base_url = BASE_URL + "screener.ashx?"

    filters_list: list[str] = []
    for key, value in filters_tuple:
        # Check if key exists in any of the imported filter data
        classes_to_check = [Fundamental_Params, Descriptive_Params, Technical_Params]
        for cls in classes_to_check:
            for attr, attr_value in cls.__dict__.items():
                if isinstance(attr_value, list) and key in attr_value:
                    filters_list.append(f"{key}_{value}")

    filters_str = ",".join(filters_list)
    query_url = f"{base_url}v={v}&f={filters_str}&ft={ft}"
    return query_url


