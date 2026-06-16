import json
from pathlib import Path

import typer
from rich.table import Table

from ghealth.api import GHealthApiClient
from ghealth.commands.context import CliState
from ghealth.commands.shared import (
    apply_list_limit,
    read_json_body,
    require_cloud_platform_scope,
    require_confirmation,
    run_with_api_client,
    subscriber_payload,
    subscription_payload,
    validate_limit,
    validate_subscriber_name,
    validate_subscription_name,
)
from ghealth.output import emit_list_by_format, emit_object_by_format, print_cli_error

subscribers_app = typer.Typer(help="Manage Google Health webhook subscribers")
subscriptions_app = typer.Typer(help="Manage Google Health webhook subscriptions")


@subscribers_app.command(name="list")
def subscribers_list(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", help="Google Cloud project ID or projects/{project}."),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of subscribers per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of subscribers to return."),
) -> None:
    """List webhook subscribers for a Google Cloud project."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)
    require_cloud_platform_scope(state)

    def run(client: GHealthApiClient) -> None:
        if all_pages:
            data = client.list_all_subscribers(project, page_size=page_size, limit=limit)
        else:
            data = client.list_subscribers(project, page_size=page_size, page_token=page_token)
            data = apply_list_limit(data, "subscribers", limit)
        emit_list_by_format(state, data, "subscribers", table_builder=_subscribers_table)

    run_with_api_client(state, run)


@subscribers_app.command(name="create")
def subscribers_create(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", help="Google Cloud project ID or projects/{project}."),
    endpoint_uri: str | None = typer.Option(
        None, "--endpoint-uri", help="Public HTTPS webhook endpoint URI."
    ),
    data_types: str | None = typer.Option(None, "--data-types", help="Comma-separated data type IDs."),
    authorization_secret: str | None = typer.Option(
        None,
        "--authorization-secret",
        help="Full Authorization header value sent to the webhook endpoint.",
    ),
    subscription_create_policy: str = typer.Option(
        "MANUAL",
        "--subscription-create-policy",
        help="Subscription creation policy: MANUAL or AUTOMATIC.",
    ),
    subscriber_id: str | None = typer.Option(None, "--subscriber-id", help="Optional subscriber ID."),
    body: Path | None = typer.Option(None, "--body", help="Path to raw CreateSubscriberPayload JSON."),
) -> None:
    """Create a webhook subscriber."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    if body is not None:
        payload = read_json_body(state, body)
    else:
        if not endpoint_uri or not data_types or not authorization_secret:
            print_cli_error(
                state,
                "subscriber_create_fields_required",
                "Pass --endpoint-uri, --data-types, and --authorization-secret, or pass --body.",
                exit_code=2,
            )
        payload = subscriber_payload(
            endpoint_uri=endpoint_uri,
            data_types=data_types,
            authorization_secret=authorization_secret,
            subscription_create_policy=subscription_create_policy,
        )

    def run(client: GHealthApiClient) -> None:
        data = client.create_subscriber(project, payload, subscriber_id=subscriber_id)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Create Subscriber Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@subscribers_app.command(name="update")
def subscribers_update(
    ctx: typer.Context,
    subscriber_name: str = typer.Argument(..., help="Full subscriber resource name."),
    body: Path = typer.Option(..., "--body", help="Path to Subscriber JSON body."),
    update_mask: str | None = typer.Option(None, "--update-mask", help="Comma-separated field mask."),
) -> None:
    """Update a webhook subscriber."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    validate_subscriber_name(state, subscriber_name)
    payload = read_json_body(state, body)

    def run(client: GHealthApiClient) -> None:
        data = client.update_subscriber(subscriber_name, payload, update_mask=update_mask)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Update Subscriber Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@subscribers_app.command(name="delete")
def subscribers_delete(
    ctx: typer.Context,
    subscriber_name: str = typer.Argument(..., help="Full subscriber resource name."),
    force: bool = typer.Option(False, "--force", help="Delete child subscriptions too."),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion without prompting."),
) -> None:
    """Delete a webhook subscriber."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    validate_subscriber_name(state, subscriber_name)
    require_confirmation(state, yes=yes, action="Delete subscriber", target=subscriber_name)

    def run(client: GHealthApiClient) -> None:
        data = client.delete_subscriber(subscriber_name, force=force)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Delete Subscriber Operation", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@subscriptions_app.command(name="list")
def subscriptions_list(
    ctx: typer.Context,
    subscriber: str = typer.Option(..., "--subscriber", help="Full subscriber resource name."),
    filter_expr: str | None = typer.Option(None, "--filter", help="AIP-160 filter, e.g. user or dataType."),
    page_size: int | None = typer.Option(None, "--page-size", help="Number of subscriptions per page."),
    page_token: str | None = typer.Option(None, "--page-token", help="Token for the next page."),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of subscriptions to return."),
) -> None:
    """List subscriptions for a subscriber."""
    state: CliState = ctx.obj
    limit = validate_limit(state, limit)
    require_cloud_platform_scope(state)
    validate_subscriber_name(state, subscriber)

    def run(client: GHealthApiClient) -> None:
        if all_pages:
            data = client.list_all_subscriptions(
                subscriber,
                filter=filter_expr,
                page_size=page_size,
                limit=limit,
            )
        else:
            data = client.list_subscriptions(
                subscriber,
                filter=filter_expr,
                page_size=page_size,
                page_token=page_token,
            )
            data = apply_list_limit(data, "subscriptions", limit)
        emit_list_by_format(state, data, "subscriptions", table_builder=_subscriptions_table)

    run_with_api_client(state, run)


@subscriptions_app.command(name="create")
def subscriptions_create(
    ctx: typer.Context,
    subscriber: str = typer.Option(..., "--subscriber", help="Full subscriber resource name."),
    user: str | None = typer.Option(None, "--user", help="User resource name, e.g. users/{healthUserId}."),
    data_types: str | None = typer.Option(None, "--data-types", help="Comma-separated data type IDs."),
    subscription_id: str | None = typer.Option(None, "--subscription-id", help="Optional subscription ID."),
    body: Path | None = typer.Option(None, "--body", help="Path to raw CreateSubscriptionPayload JSON."),
) -> None:
    """Create a user subscription for a subscriber."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    validate_subscriber_name(state, subscriber)
    if body is not None:
        payload = read_json_body(state, body)
    else:
        if not user or not data_types:
            print_cli_error(
                state,
                "subscription_create_fields_required",
                "Pass --user and --data-types, or pass --body.",
                exit_code=2,
            )
        payload = subscription_payload(user=user, data_types=data_types)

    def run(client: GHealthApiClient) -> None:
        data = client.create_subscription(subscriber, payload, subscription_id=subscription_id)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _subscription_table("Subscription", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@subscriptions_app.command(name="update")
def subscriptions_update(
    ctx: typer.Context,
    subscription_name: str = typer.Argument(..., help="Full subscription resource name."),
    body: Path = typer.Option(..., "--body", help="Path to Subscription JSON body."),
    update_mask: str | None = typer.Option(None, "--update-mask", help="Comma-separated field mask."),
) -> None:
    """Update a subscription."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    validate_subscription_name(state, subscription_name)
    payload = read_json_body(state, body)

    def run(client: GHealthApiClient) -> None:
        data = client.update_subscription(subscription_name, payload, update_mask=update_mask)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _subscription_table("Subscription", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


@subscriptions_app.command(name="delete")
def subscriptions_delete(
    ctx: typer.Context,
    subscription_name: str = typer.Argument(..., help="Full subscription resource name."),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion without prompting."),
) -> None:
    """Delete a subscription."""
    state: CliState = ctx.obj
    require_cloud_platform_scope(state)
    validate_subscription_name(state, subscription_name)
    require_confirmation(state, yes=yes, action="Delete subscription", target=subscription_name)

    def run(client: GHealthApiClient) -> None:
        data = client.delete_subscription(subscription_name)
        emit_object_by_format(
            state,
            data,
            table_builder=lambda d: _operation_table("Delete Subscription", d),
            raw_builder=lambda d: [json.dumps(d)],
        )

    run_with_api_client(state, run)


def _subscribers_table(items: list[dict]) -> Table:
    table = Table(title="Subscribers")
    table.add_column("Subscriber ID", style="cyan")
    table.add_column("Endpoint URI", style="magenta")
    table.add_column("Data Types", style="green")
    for item in items:
        table.add_row(
            _resource_leaf(item.get("name", "")),
            item.get("endpointUri", ""),
            _subscriber_data_types(item),
        )
    return table


def _subscriber_data_types(item: dict) -> str:
    configs = item.get("subscriberConfigs")
    if not isinstance(configs, list):
        return ""
    data_types: list[str] = []
    for config in configs:
        if isinstance(config, dict) and isinstance(config.get("dataTypes"), list):
            data_types.extend(str(data_type) for data_type in config["dataTypes"])
    return ", ".join(data_types)


def _resource_leaf(resource_name: str) -> str:
    if not resource_name:
        return ""
    return resource_name.rstrip("/").rsplit("/", maxsplit=1)[-1]


def _subscriptions_table(items: list[dict]) -> Table:
    table = Table(title="Subscriptions")
    table.add_column("Subscription ID", style="cyan")
    table.add_column("User", style="magenta")
    table.add_column("Data Types", style="green")
    for item in items:
        table.add_row(
            _resource_leaf(item.get("name", "")), item.get("user", ""), ", ".join(item.get("dataTypes", []))
        )
    return table


def _subscription_table(title: str, data: dict) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    for key in ("name", "user", "dataTypes"):
        if key in data:
            value = data[key]
            table.add_row(key, ", ".join(value) if isinstance(value, list) else str(value))
    return table


def _operation_table(title: str, data: dict) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    for key, value in sorted(data.items()):
        if isinstance(value, (dict, list)):
            table.add_row(key, json.dumps(value))
        else:
            table.add_row(key, str(value))
    return table
