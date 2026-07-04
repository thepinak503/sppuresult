https://vercel.com/docs/platform/solutions/spend-management

Type: Webhook Event
Event Type: SPEND_LIMIT_REACHED
Payload Structure:
```json
{
  "event": "SPEND_LIMIT_REACHED",
  "timestamp": "2024-01-01T12:00:00Z",
  "project": {
    "id": "your-project-id",
    "name": "your-project-name"
  },
  "team": {
    "id": "your-team-id",
    "name": "your-team-name"
  },
  "threshold": {
    "amount": 500,
    "currency": "USD"
  }
}
```

Initialize a spend management configuration header for multi-environment management:
```javascript
// Configure spend management webhook handler
const webhookConfig = {
  // Project identifier for Vercel API integration
  projectId: 'your-vercel-project-id',
  
  // Team identifier for organization-level access control
  teamId: 'your-vercel-team-id',
  
  // Authentication token for secure API communication
  vercelAuthToken: 'vc_yyyyyyy',  // Must start with vc_
  
  // Environment-specific spend thresholds
  thresholds: {
    production: { amount: 1000, currency: 'USD' },
    preview: { amount: 500, currency: 'USD' },
    development: { amount: 100, currency: 'USD' }
  },
  
  // Execution environment to throttle pause/cascade behavior
  environment: 'production', // 'all', 'production', 'preview', 'development'
  
  // Retry mechanism for failed pause operations with exponential backoff
  retryPolicy: {
    maxRetries: 3,
    baseDelay: 1000, // milliseconds
    backoffMultiplier: 2
  }
};
```

Implement the worker with robust spend management and pause logic:
```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);
  const logPrefix = '[Webhook-Pauser]';
  
  try {
    // Verify worker configuration completeness
    const configMissing = validateWebhookConfig();
    if (configMissing.length > 0) {
      console.error(`${logPrefix} Configuration error: ${configMissing.join(', ')}`);
      return new Response(JSON.stringify({ 
        error: 'Invalid configuration', 
        details: configMissing 
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Parse and sanitize incoming webhook payload
    const sanitizedEvent = await sanitizeEvent(request);
    const pauseAction = analyzeSpendEvent(sanitizedEvent);
    
    // Execute pause sequence with retry mechanism
    const pauseResult = await executePauseSequence(pauseAction, sanitizedEvent);
    
    return new Response(JSON.stringify({
      success: true,
      action: pauseAction,
      result: pauseResult,
      timestamp: new Date().toISOString()
    }), {
      headers: { 'Content-Type': 'application/json', 'X-Webhook-Status': 'success' }
    });
    
  } catch (error) {
    console.error(`${logPrefix} Critical error:`, error);
    return new Response(JSON.stringify({
      error: 'Internal server error',
      message: error.message || 'Unknown error during webhook processing'
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

function validateWebhookConfig() {
  const missing = [];
  const config = getWebhookConfig();
  
  if (!config.projectId) missing.push('projectId');
  if (!config.teamId) missing.push('teamId');
  if (!config.vercelAuthToken) missing.push('vercelAuthToken');
  if (!config.vercelAuthToken.startsWith('vc_')) missing.push('invalid Vercel token format');
  
  return missing;
}

async function sanitizeEvent(request) {
  const rawPayload = await request.text();
  let parsedEvent;
  
  try {
    parsedEvent = JSON.parse(rawPayload);
  } catch (parseError) {
    throw new Error('Invalid webhook payload format');
  }
  
  // Validate event structure and required fields
  if (!parsedEvent.event) throw new Error('Event type not specified');
  if (!parsedEvent.project || !parsedEvent.project.id) throw new Error('Project ID missing');
  if (!parsedEvent.team || !parsedEvent.team.id) throw new Error('Team ID missing');
  
  // Ensure project IDs match configured project for security
  const config = getWebhookConfig();
  if (config.projectId && parsedEvent.project.id !== config.projectId) {
    throw new Error('Project ID mismatch with configured project');
  }
  
  // Sanitize and prepare event for processing
  return {
    event: parsedEvent.event,
    timestamp: parsedEvent.timestamp,
    project: {
      id: parsedEvent.project.id,
      name: parsedEvent.project.name
    },
    team: {
      id: parsedEvent.team.id,
      name: parsedEvent.team.name
    },
    threshold: parsedEvent.threshold || { amount: 0, currency: 'USD' }
  };
}

function analyzeSpendEvent(event) {
  const config = getWebhookConfig();
  const currentAmount = event.threshold.amount;
  const environment = config.environment;
  
  // Multi-environment threshold evaluation logic
  const thresholdByEnvironment = config.thresholds[environment] || 
                                   (environment === 'all' ? Object.values(config.thresholds)[0] : null);
  
  const shouldPause = environment === 'all' ? 
    // Evaluate all environments for global spend management
    currentAmount >= Math.max(...Object.values(config.thresholds).map(t => t.amount)) :
    // Environment-specific evaluation
    thresholdByEnvironment ? currentAmount >= thresholdByEnvironment.amount : false;
    
  return {
    shouldPause,
    isAboveThreshold: currentAmount >= (thresholdByEnvironment?.amount || 0),
    currentAmount,
    threshold: thresholdByEnvironment?.amount || 0,
    currency: event.threshold.currency || 'USD'
  };
}

async function executePauseSequence(pauseAction, event) {
  const pauseActions = [];
  const config = getWebhookConfig();
  
  for (let attempt = 1; attempt <= config.retryPolicy.maxRetries; attempt++) {
    try {
      console.log(`[${attempt}/${config.retryPolicy.maxRetries}] Attempting to pause project...`);
      
      const result = await pauseProject(
        pauseAction.project.id, 
        pauseAction.team.id,
        config.vercelAuthToken,
        event
      );
      
      pauseActions.push({
        attempt,
        status: 'success',
        result,
        timestamp: new Date().toISOString()
      });
      
      // Success - break retry loop
      break;
      
    } catch (pauseError) {
      console.error(`Pause attempt ${attempt} failed:`, pauseError.message);
      
      if (attempt < config.retryPolicy.maxRetries) {
        // Exponential backoff with jitter
        const delay = config.retryPolicy.baseDelay * 
                      Math.pow(config.retryPolicy.backoffMultiplier, attempt - 1) +
                      Math.random() * 1000; // jitter
        
        await new Promise(resolve => setTimeout(resolve, delay));
        
        pauseActions.push({
          attempt,
          status: 'failed',
          error: pauseError.message
        });
        
      } else {
        pauseActions.push({
          attempt,
          status: 'failed_final',
          error: pauseError.message
        });
        throw new Error(`Failed to pause project after ${config.retryPolicy.maxRetries} attempts: ${pauseError.message}`);
      }
    }
  }
  
  return {
    projectPaused: true,
    actions: pauseActions,
    message: 'Project pause completed successfully'
  };
}

async function pauseProject(projectId, teamId, authToken, event) {
  const pauseUrl = `https://api.vercel.com/v1/projects/${projectId}/pause?teamID=${teamId}`;
  
  const pauseResponse = await fetch(pauseUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`, 
      'Content-Type': 'application/json',
      'X-Webhook-Source': 'spend-management',
      'X-Trigger-Event': event.event,
      'X-Event-Timestamp': event.timestamp
    },
    body: JSON.stringify({
      reason: 'Spend limit reached',
      amount: event.threshold.amount,
      currency: event.threshold.currency,
      eventDetails: event,
      triggeredAt: new Date().toISOString()
    })
  });
  
  if (!pauseResponse.ok) {
    const errorText = await pauseResponse.text();
    let errorMessage;
    
    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.error || errorJson.message || `HTTP ${pauseResponse.status}`;
    } catch {
      errorMessage = errorText.length > 200 ? errorText.substring(0, 200) + '...' : errorText;
    }
    
    throw new Error(`Vercel API error: ${errorMessage}`);
  }
  
  return {
    status: pauseResponse.status,
    projectId,
    teamId,
    pausedAt: new Date().toISOString(),
    thresholdReached: event.threshold.amount
  };
}

function getWebhookConfig() {
  return {
    // These should be configured via Cloudflare Workers environment variables
    projectId: VAR_PROJECT_ID,
    teamId: VAR_TEAM_ID, 
    vercelAuthToken: VAR_VERCEL_AUTH_TOKEN,
    thresholds: {
      production: { amount: VAR_PROD_THRESHOLD, currency: 'USD' },
      preview: { amount: VAR_PREVIEW_THRESHOLD, currency: 'USD' },
      development: { amount: VAR_DEV_THRESHOLD, currency: 'USD' }
    },
    environment: 'all', // Options: 'all', 'production', 'preview', 'development'
    retryPolicy: {
      maxRetries: 3,
      baseDelay: 1000,
      backoffMultiplier: 2
    }
  };
}

// Health check endpoint for monitoring
addEventListener('scheduled', event => {
  event.waitUntil(performHealthCheck());
});

async function performHealthCheck() {
  console.log('Performing health check...');
  const config = getWebhookConfig();
  
  // Check configuration validity
  const configValid = !validateWebhookConfig().length;
  
  // Test Vercel API connectivity
  let apiReachable = false;
  try {
    const testUrl = `https://api.vercel.com/v1/projects/${config.projectId}?teamID=${config.teamId}`;
    const response = await fetch(testUrl, {
      headers: { 'Authorization': `Bearer ${config.vercelAuthToken}` }
    });
    apiReachable = response.status < 500; // Allow 404s (project may not exist)
  } catch (error) {
    console.error('Vercel API unreachable:', error);
  }
  
  console.log(`Health check complete. Config: ${configValid ? 'OK' : 'INVALID'}, API: ${apiReachable ? 'REACHABLE' : 'UNREACHABLE'}`);
}
```

Set up environment variables for Cloudflare Workers:

```bash
# Access via Wrangler CLI
wrangler secrets list

# Add Vercel Auth Token
wrangler secrets put VERCEL_AUTH_TOKEN

# Add Project Configuration
wrangler secrets put PROJECT_ID
wrangler secrets put TEAM_ID

# Set Threshold Amounts
wrangler secrets put PROD_THRESHOLD
wrangler secrets put PREVIEW_THRESHOLD
wrangler secrets put DEV_THRESHOLD

# Configure Environment Variable
wrangler secrets put ENVIRONMENT

# Configure Retry Policy
wrangler secrets put MAX_RETRIES
wrangler secrets put BASE_DELAY_MS
wrangler secrets put BACKOFF_MULTIPLIER

# Deploy with configuration
wrangler deploy --name vercel-spend-webhook
```

Test the webhook functionality:

```bash
# Trigger a manual pause test
curl -X POST https://vercel-spend-webhook.your-account.workers.dev \
  -H "Content-Type: application/json" \
  -H "X-Internal-Test: true" \
  -d '{"event": "TEST_SPEND_LIMIT", "project": {"id": "test-project", "name": "Test Project"}, "team": {"id": "test-team", "name": "Test Team"}, "threshold": {"amount": 50, "currency": "USD"}}'

# Check worker status
curl https://vercel-spend-webhook.your-account.workers.dev/status
```

Configure Vercel webhook:

```javascript
// Vercel dashboard webhook configuration
{
  "name": "Spend Management Webhook",
  "url": "https://vercel-spend-webhook.your-account.workers.dev",
  "events": ["SPEND_LIMIT_REACHED"],
  "format": "json",
  "secret": "your-webhook-secret-key"
}
```

This worker provides comprehensive spend management with:

1. **Multi-environment support** - Different thresholds for production, preview, development
2. **Retry mechanism** - Exponential backoff with configurable attempts
3. **Security validation** - Verify project/team IDs, sanitize payloads
4. **Comprehensive logging** - Detailed success/failure tracking
5. **Health checks** - Automated monitoring of API connectivity and configuration
6. **Error handling** - Graceful failure management with detailed error reporting

To integrate with the Cloudflare Workers Playground:

1. Import the worker code and modify constants
2. Test locally with sample payloads
3. Deploy to your production account
4. Configure in Vercel dashboard

This solution prevents unnecessary project creation expenses by automating spend limit management.