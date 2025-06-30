#!/usr/bin/env node

/**
 * Insight Digger MCP Bridge
 * 
 * A lightweight bridge that translates between standard MCP protocol 
 * and the existing enterprise-grade MCP Client Flask API.
 * 
 * This preserves all existing functionality:
 * - JWT authentication and session management
 * - Intelligent parameter caching and injection
 * - Multi-step workflow optimization
 * - Enterprise security and compliance features
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

// Configuration
const MCP_CLIENT_URL = process.env.MCP_CLIENT_URL || 'https://internal.sandsiv.com/data-narrator-mcp';
const BRIDGE_LOGGING_ENABLED = process.env.BRIDGE_LOGGING_ENABLED === 'true'; // Disabled by default

// Bridge session state
let bridgeSession = {
  sessionId: null,
  authenticated: false,
  availableTools: [],
  workflowGuidance: null
};

// Cache for /tools-schema response (never changes)
let cachedToolsSchema = null;

// Create MCP server
const server = new Server(
  {
    name: "insight-digger-mcp-bridge",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * Simple logging function.
 */
function log(message) {
  if (!BRIDGE_LOGGING_ENABLED) return;
  console.error(`[BRIDGE] ${new Date().toISOString()}: ${message}`);
}

/**
 * Generate unique session ID for this bridge instance
 */
function generateSessionId() {
  return `bridge-${uuidv4()}`;
}

/**
 * Setup authentication with the existing MCP client
 */
async function setupAuthentication(args) {
  const { apiUrl, jwtToken } = args;
  
  // Log authentication request
  log('Authentication request received.');
  
  if (!apiUrl || !jwtToken) {
    throw new Error("Both apiUrl and jwtToken are required");
  }

  // Generate session ID for this bridge instance
  bridgeSession.sessionId = generateSessionId();
  
  try {
    // Initialize session with existing MCP client
    log(`Initializing session ${bridgeSession.sessionId} with MCP client.`);
    console.error(`[BRIDGE] Initializing session ${bridgeSession.sessionId} with MCP client`);
    const initPayload = {
      session_id: bridgeSession.sessionId,
      apiUrl: apiUrl,
      jwtToken: jwtToken
    };
    
    const initResponse = await axios.post(`${MCP_CLIENT_URL}/init`, initPayload);

    // Get available tools from existing MCP client
    log(`Fetching available tools for session ${bridgeSession.sessionId}.`);
    console.error(`[BRIDGE] Fetching available tools for session ${bridgeSession.sessionId}`);
    const toolsPayload = { session_id: bridgeSession.sessionId };
    
    const toolsResponse = await axios.post(`${MCP_CLIENT_URL}/tools`, toolsPayload);

    // Store tools and workflow guidance for dynamic registration
    bridgeSession.availableTools = toolsResponse.data.tools || [];
    bridgeSession.workflowGuidance = toolsResponse.data.workflow_guidance;
    bridgeSession.authenticated = true;

    log(`Authentication successful. ${bridgeSession.availableTools.length} tools available.`);
    console.error(`[BRIDGE] Authentication successful. ${bridgeSession.availableTools.length} tools available.`);

    const result = {
      status: "success",
      message: `Authentication successful! ${bridgeSession.availableTools.length} analysis tools are now available.`,
      sessionId: bridgeSession.sessionId
    };
    
    return result;

  } catch (error) {
    console.error(`[BRIDGE] Authentication failed:`, error.message);
    
    // Log authentication failure
    log(`Authentication failed: ${error.message}`);
    
    // Reset session state on failure
    bridgeSession = {
      sessionId: null,
      authenticated: false,
      availableTools: [],
      workflowGuidance: null
    };

    throw new Error(`Authentication failed: ${error.response?.data?.error || error.message}`);
  }
}

/**
 * Proxy tool call to existing MCP client (preserves all caching logic)
 */
async function proxyToolCall(toolName, args) {
  if (!bridgeSession.authenticated) {
    throw new Error("Authentication required. Please call setup_authentication first.");
  }

  // Log tool call request
  log(`Proxying tool call: ${toolName}`);

  try {
    console.error(`[BRIDGE] Proxying tool call: ${toolName}`);
    
    const requestPayload = {
      session_id: bridgeSession.sessionId,
      tool: toolName,
      params: args || {}
    };
    
    const response = await axios.post(`${MCP_CLIENT_URL}/call-tool`, requestPayload);

    // Log tool call success
    log(`Tool call '${toolName}' successful.`);

    return response.data;

  } catch (error) {
    console.error(`[BRIDGE] Tool call failed for ${toolName}:`, error.message);
    
    // Log tool call error
    log(`Tool call failed for ${toolName}: ${error.message}`);
    
    throw new Error(`Tool execution failed: ${error.response?.data?.error || error.message}`);
  }
}

/**
 * Get tools schema from Flask API (cached forever)
 */
async function getToolsSchema() {
  if (cachedToolsSchema) {
    log('Using cached tools schema.');
    return cachedToolsSchema;
  }
  
  try {
    log('Fetching tools schema from /tools-schema');
    console.error(`[BRIDGE] Fetching tools schema from /tools-schema`);
    
    const response = await axios.get(`${MCP_CLIENT_URL}/tools-schema`);
    cachedToolsSchema = response.data;
    
    return cachedToolsSchema;
  } catch (error) {
    console.error(`[BRIDGE] Failed to fetch tools schema:`, error.message);
    
    log(`Failed to fetch tools schema: ${error.message}`);
    
    return { system_info: null, tools: [] };
  }
}

/**
 * Create enhanced authentication tool description with system context
 */
async function createAuthenticationTool() {
  const schema = await getToolsSchema();
  const systemInfo = schema.system_info;
  
  let description = 'Setup authentication credentials for Sandsiv+ Insight Digger. This must be called FIRST before any analysis tools become available. Requires your API URL and JWT token.';
  
  if (systemInfo) {
    description += `\n\n**About This System:**\n`;
    description += `- **System**: ${systemInfo.system_name} (${systemInfo.system_type})\n`;
    description += `- **Purpose**: ${systemInfo.purpose}\n`;
    
    if (systemInfo.when_to_use && systemInfo.when_to_use.length > 0) {
      description += `\n**When to Use This System:**\n`;
      systemInfo.when_to_use.forEach(use => {
        description += `- ${use}\n`;
      });
    }
    
    if (systemInfo.capabilities && systemInfo.capabilities.length > 0) {
      description += `\n**Capabilities:**\n`;
      systemInfo.capabilities.forEach(capability => {
        description += `- ${capability}\n`;
      });
    }
    
    if (systemInfo.workflow_overview) {
      description += `\n**Workflow**: ${systemInfo.workflow_overview}`;
    }
  }

  return {
    name: 'setup_authentication',
    description: description,
    inputSchema: {
      type: 'object',
      properties: {
        apiUrl: {
          type: 'string',
          description: 'Your Sandsiv+ API base URL (e.g., https://your-domain.sandsiv.com)'
        },
        jwtToken: {
          type: 'string',
          description: 'Your JWT authentication token for the Sandsiv+ platform'
        }
      },
      required: ['apiUrl', 'jwtToken']
    }
  };
}

/**
 * Enhance tool descriptions with workflow guidance after authentication
 */
function enhanceToolsWithWorkflowGuidance(tools) {
  if (!bridgeSession.workflowGuidance?.workflow) {
    log('Skipping workflow enhancement: no guidance available.');
    return tools;
  }

  const workflow = bridgeSession.workflowGuidance.workflow;
  
  log('Starting workflow enhancement for tool descriptions.');
  
  // Create comprehensive workflow description
  let workflowDescription = `\n\n**📋 RECOMMENDED WORKFLOW**\n`;
  workflowDescription += `${workflow.recommended_workflow?.description || ''}\n\n`;
  
  if (workflow.recommended_workflow?.steps) {
    workflow.recommended_workflow.steps.forEach(step => {
      workflowDescription += `**Step ${step.step}: ${step.description}**\n`;
      workflowDescription += `- Tool: \`${step.tool}\`\n`;
      workflowDescription += `- Guidance: ${step.guidance}\n\n`;
    });
  }
  
  if (workflow.important_notes && workflow.important_notes.length > 0) {
    workflowDescription += `**⚠️ IMPORTANT NOTES:**\n`;
    workflow.important_notes.forEach(note => {
      workflowDescription += `- ${note}\n`;
    });
  }

  // Add workflow guidance to the first analysis tool's description
  const enhancedTools = tools.map(tool => {
    // Add to the first non-auth tool (typically list_sources)
    if (tool.name !== 'setup_authentication' && tool === tools.find(t => t.name !== 'setup_authentication')) {
      const enhancedTool = {
        ...tool,
        description: tool.description + workflowDescription
      };
      
      log(`Applied workflow guidance to tool: ${tool.name}`);
      
      return enhancedTool;
    }
    return tool;
  });

  log('Completed workflow enhancement.');

  return enhancedTools;
}

/**
 * Get all available tools (including unauthenticated ones marked as requiring auth)
 */
async function getAllAvailableTools() {
  const schema = await getToolsSchema();
  return schema.tools || [];
}

/**
 * List available tools (proactive approach - show all tools, mark unauthenticated ones)
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  // Log tools list request
  log('List tools request received.');

  // Create authentication tool with enhanced description
  const authTool = await createAuthenticationTool();
  const tools = [authTool];

  if (bridgeSession.authenticated && bridgeSession.availableTools.length > 0) {
    // User is authenticated - show enhanced tools with workflow guidance
    const rawTools = [...bridgeSession.availableTools];
    
    // Enhance tools with detailed workflow guidance
    const enhancedTools = enhanceToolsWithWorkflowGuidance(rawTools);
    
    tools.push(...enhancedTools);
  } else {
    // User is not authenticated - show all tools but mark them as requiring authentication
    const allTools = await getAllAvailableTools();
    
    if (allTools.length > 0) {
      const unauthenticatedTools = allTools.map(tool => {
        // Remove null annotations to avoid MCP SDK validation errors
        const cleanTool = { ...tool };
        if (cleanTool.annotations === null) {
          delete cleanTool.annotations;
        }
        
        return {
          ...cleanTool,
          description: `🔒 **[Requires Authentication]** ${cleanTool.description}\n\n⚠️ **Please authenticate first** by calling the \`setup_authentication\` tool above. This tool will become fully functional after authentication.`
        };
      });
      
      log('Returning list of unauthenticated tools.');
      
      tools.push(...unauthenticatedTools);
    }
  }

  // Log tools list response
  log(`Returning ${tools.length} tools. Authenticated: ${bridgeSession.authenticated}`);

  return { tools };
});

/**
 * Handle tool calls
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // Log incoming tool call
  log(`Received MCP tool call for: ${name}`);

    try {
    if (name === 'setup_authentication') {
      const result = await setupAuthentication(args);
      
      // Log MCP response
      log(`MCP response for 'setup_authentication' sent.`);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      };
    } else if (!bridgeSession.authenticated) {
      // Handle calls to unauthenticated tools
      const authRequiredResponse = {
        status: 'error',
        error: `Authentication required. Please call 'setup_authentication' first to access the '${name}' tool.`,
        toolRequested: name,
        authenticationNeeded: true
      };
      
      log(`MCP auth required response for tool '${name}' sent.`);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(authRequiredResponse, null, 2)
          }
        ]
      };
    } else {
      // Proxy authenticated tool calls to existing MCP client
      const result = await proxyToolCall(name, args);
      
      // Log MCP response
      log(`MCP response for proxied tool '${name}' sent.`);
      
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2)
            }
          ]
        };
    }
  } catch (error) {
    // Log MCP error response
    log(`Error handling MCP tool call for '${name}': ${error.message}`);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            status: 'error',
            error: error.message
          }, null, 2)
        }
      ],
      isError: true
    };
  }
});

/**
 * Cleanup on shutdown
 */
async function cleanup() {
  if (bridgeSession.authenticated && bridgeSession.sessionId) {
    try {
      console.error(`[BRIDGE] Cleaning up session ${bridgeSession.sessionId}`);
      await axios.post(`${MCP_CLIENT_URL}/shutdown`, {
        session_id: bridgeSession.sessionId
      });
    } catch (error) {
      console.error(`[BRIDGE] Cleanup failed:`, error.message);
    }
  }
}

// Handle process termination
process.on('SIGINT', async () => {
  await cleanup();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await cleanup();
  process.exit(0);
});

/**
 * Start the bridge server
 */
async function main() {
  console.error(`[BRIDGE] Starting Insight Digger MCP Bridge`);
  console.error(`[BRIDGE] Connecting to MCP Client at: ${MCP_CLIENT_URL}`);
  console.error(`[BRIDGE] Logging is ${BRIDGE_LOGGING_ENABLED ? 'enabled' : 'disabled'}.`);
  
  // Log bridge startup
  log('Bridge starting up.');
  
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.error(`[BRIDGE] Bridge ready. Waiting for authentication...`);
}

main().catch((error) => {
  console.error(`[BRIDGE] Fatal error:`, error);
  process.exit(1);
}); 