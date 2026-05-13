import click


@click.group(invoke_without_command=True)
@click.option("--history", "--hist", is_flag=True, help="Use filters of recent search.")
@click.option("--debug", is_flag=True, help="Display details logging.")
@click.option(
    "--scrape-link",
    default="",
    help=(
        "Direct Finviz screener URL; bypasses interactive filter selection. "
        "Mutually exclusive with --history."
    ),
)
@click.pass_context
def run_main(
    ctx: click.Context,
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
) -> None:
    """
    Welcome to the Stock Screener CLI!
    """
    # --history and --scrape-link are alternative input modes; combining them is undefined.
    # Inline check (instead of a Click callback) so both flags are guaranteed parsed.
    if history and scrape_link:
        raise click.UsageError(
            "--history and --scrape-link are mutually exclusive; pick one input mode."
        )

    click.echo("Welcome to the Stock Screener CLI!")
    from .main import run_stock_screener

    if ctx.invoked_subcommand is None:
        run_stock_screener(history=history, debug=debug, scrape_link=scrape_link)


if __name__ == "__main__":
    run_main()
