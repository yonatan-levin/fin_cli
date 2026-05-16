from ..resource.params.const import BASE_URL
from ..resource.params.descriptive_params import Descriptive_Params
from ..resource.params.fundamental_params import Fundamental_Params
from ..resource.params.technical_params import Technical_Params


def build_stock_screener_query(filters_tuple, v=111, ft=2):
    base_url = BASE_URL + "screener.ashx?"

    filters_list = []
    for key, value in filters_tuple:
        # Check if key exists in any of the imported filter data

        classes_to_check = [Fundamental_Params, Descriptive_Params, Technical_Params]

        for cls in classes_to_check:
            for _attr, attr_value in cls.__dict__.items():
                if isinstance(attr_value, list) and key in attr_value:
                    filters_list.append(f"{key}_{value}")

    # Joining the filters with commas
    filters_str = ",".join(filters_list)

    # Constructing the full URL. The constructed URL is logged downstream by
    # `fincli.app.main.run_stock_screener` ("Fetching HTML from {quarry}"), so
    # this builder stays side-effect-free and logger-free — keeping the layer
    # transport-agnostic. (Was a `click.echo` until VERIFIER caught it as a
    # stdout pollutant for the `--output -` pipeline path.)
    query_url = f"{base_url}v={v}&f={filters_str}&ft={ft}"
    return query_url
