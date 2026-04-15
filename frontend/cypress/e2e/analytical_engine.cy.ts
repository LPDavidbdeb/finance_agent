describe('Financial Inference Engine E2E', () => {
  beforeEach(() => {
    // Mock initial state: idle with some old facts
    cy.intercept('GET', '**/api/analysis/engine/status', {
      statusCode: 200,
      body: {
        status: 'idle',
        last_computed_at: '2026-04-10T10:00:00Z',
        total_facts: 12000
      }
    }).as('getInitialStatus');

    // Mock initial empty insights
    cy.intercept('GET', '**/api/analysis/insights/top', {
      statusCode: 200,
      body: []
    }).as('getEmptyInsights');

    // Mock trigger endpoint
    cy.intercept('POST', '**/api/analysis/engine/trigger', {
      statusCode: 200,
      body: { message: 'Engine triggered' }
    }).as('triggerEngine');
  });

  it('navigates to analysis, triggers the engine, polls, and renders results', () => {
    cy.visit('/analysis');
    cy.wait(['@getInitialStatus', '@getEmptyInsights']);

    // Check initial UI
    cy.contains('Idle / Ready').should('be.visible');
    cy.contains('12,000').should('be.visible');
    cy.contains('No significant insights detected').should('be.visible');

    // Start rebuilding
    // We will change the mock for the NEXT status calls to return 'syncing'
    cy.intercept('GET', '**/api/analysis/engine/status', {
      statusCode: 200,
      body: {
        status: 'syncing',
        last_computed_at: '2026-04-10T10:00:00Z',
        total_facts: 12000
      }
    }).as('getSyncingStatus');

    cy.contains('Run Analytics Engine').click();
    cy.wait('@triggerEngine');

    // Assert syncing state
    cy.contains('Syncing...').should('be.visible');
    cy.get('.animate-spin').should('be.visible');

    // Now mock completion and real data
    cy.intercept('GET', '**/api/analysis/engine/status', {
      statusCode: 200,
      body: {
        status: 'idle',
        last_computed_at: '2026-04-14T15:00:00Z',
        total_facts: 12450
      }
    }).as('getCompletedStatus');

    const mockInsights = [
      {
        id: '1',
        categoryName: 'Groceries',
        insight_score: 95,
        materiality_pct: 12.5,
        processType: 'STOCHASTIC',
        expertSummary: 'Groceries spend is showing a real growth trend driven by price increases.',
        causal_volume_pct: 2.0,
        causal_price_pct: 15.0
      },
      {
        id: '2',
        categoryName: 'Netflix',
        insight_score: 10,
        materiality_pct: 0.5,
        processType: 'DETERMINISTIC',
        expertSummary: 'Consistent monthly subscription.',
        causal_volume_pct: 0.0,
        causal_price_pct: 0.0
      }
    ];

    cy.intercept('GET', '**/api/analysis/insights/top', {
      statusCode: 200,
      body: mockInsights
    }).as('getFinalInsights');

    // Wait for the polling to pick up the idle status and refresh insights
    cy.wait('@getCompletedStatus');
    cy.wait('@getFinalInsights');

    // Truth Assertions
    cy.contains('Idle / Ready').should('be.visible');
    cy.contains('12,450').should('be.visible');
    cy.contains('Rebuild successful').should('be.visible');

    // Assert InsightCards
    cy.contains('Groceries').should('be.visible');
    
    // Check for STOCHASTIC badge
    cy.get('.bg-purple-100').contains('Stochastic').should('exist');

    // Check Causal Explanation (Price Driven since 15% > 2%)
    cy.contains('Price Driven').should('be.visible');
    cy.contains('Price:').parent().contains('15.0%');
    cy.contains('Volume:').parent().contains('2.0%');

    // Expert Summary check
    cy.contains('Groceries spend is showing a real growth trend driven by price increases.').should('be.visible');
    
    // Netflix check
    cy.contains('Netflix').should('be.visible');
    cy.get('.bg-blue-100').contains('Deterministic').should('exist');
  });
});
