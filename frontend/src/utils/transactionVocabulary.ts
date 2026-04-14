export const TRANSACTION_ROUTE_LABEL = 'Route';
export const TRANSACTION_ROUTING_RULE_LABEL = 'Create routing rule';
export const TRANSACTION_ROUTED_LABEL = 'Routed';
export const TRANSACTION_ROUTED_TO_LABEL = 'Routed to';
export const TRANSACTION_ROUTING_BACKLOG_TITLE = 'Action Required: Global Routing Backlog';
export const TRANSACTION_ROUTING_BACKLOG_DESCRIPTION =
  'Transactions that have been extracted but not yet routed or covered by a routing rule.';

export const formatRoutingRuleSuccess = (updatedCount: number) =>
  `Successfully created routing rule and auto-routed ${updatedCount} transaction(s).`;

