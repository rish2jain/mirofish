#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_URL = process.env.MIROFISH_API_URL || "http://localhost:5001";

async function apiCall(method, path, body = null) {
  const url = `${API_URL}${path}`;
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${method} ${path} failed (${res.status}): ${text}`);
  }
  return res.json();
}

// Helper to poll simulation status until complete
async function pollSimulation(simulationId, maxWaitMs = 600000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const status = await apiCall("GET", `/api/simulation/${simulationId}/run-status`);
    if (status.data?.status === "completed" || status.data?.status === "stopped") {
      return status.data;
    }
    if (status.data?.status === "failed" || status.data?.status === "error") {
      throw new Error(`Simulation failed: ${JSON.stringify(status.data)}`);
    }
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error(`Simulation ${simulationId} timed out after ${maxWaitMs}ms`);
}

const server = new McpServer({
  name: "mirofish",
  version: "0.1.0",
});

// Tool: list_templates
server.tool(
  "list_templates",
  "List available MiroFish simulation templates (regulatory impact, M&A reaction, crisis comms, etc.)",
  {},
  async () => {
    const result = await apiCall("GET", "/api/templates/");
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

// Tool: run_simulation
server.tool(
  "run_simulation",
  "Run a full MiroFish simulation pipeline: create simulation from a project, prepare agent profiles, and start the social media simulation. Returns simulation ID and status. The project must already exist (documents uploaded and graph built).",
  {
    project_id: z.string().describe("The project ID (from a previous document upload + graph build)"),
    requirement: z.string().optional().describe("Override the simulation requirement/prompt"),
    max_rounds: z.number().optional().describe("Maximum simulation rounds (default: 10)"),
    template_id: z.string().optional().describe("Template ID to use for defaults"),
    wait_for_completion: z.boolean().optional().describe("If true, poll until simulation completes (default: false)"),
  },
  async ({ project_id, requirement, max_rounds, template_id, wait_for_completion }) => {
    // Step 1: Create simulation
    const createBody = { project_id };
    if (requirement) createBody.requirement = requirement;
    if (max_rounds) createBody.max_rounds = max_rounds;
    if (template_id) createBody.template_id = template_id;

    const created = await apiCall("POST", "/api/simulation/create", createBody);
    const simId = created.data?.simulation_id || created.data?.id;
    if (!simId) throw new Error(`Failed to create simulation: ${JSON.stringify(created)}`);

    // Step 2: Prepare simulation
    await apiCall("POST", "/api/simulation/prepare", { simulation_id: simId });

    // Step 3: Start simulation
    await apiCall("POST", "/api/simulation/start", { simulation_id: simId });

    let result = { simulation_id: simId, status: "started" };

    if (wait_for_completion) {
      const finalStatus = await pollSimulation(simId);
      result = { simulation_id: simId, ...finalStatus };
    }

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// Tool: get_report
server.tool(
  "get_report",
  "Get or generate a MiroFish simulation report. If report_id is provided, fetches existing report. If simulation_id is provided, generates a new report.",
  {
    report_id: z.string().optional().describe("Existing report ID to fetch"),
    simulation_id: z.string().optional().describe("Simulation ID to generate a new report for"),
  },
  async ({ report_id, simulation_id }) => {
    if (report_id) {
      const report = await apiCall("GET", `/api/report/${report_id}`);
      return {
        content: [{ type: "text", text: JSON.stringify(report.data, null, 2) }],
      };
    }
    if (simulation_id) {
      const generated = await apiCall("POST", "/api/report/generate", { simulation_id });
      return {
        content: [{ type: "text", text: JSON.stringify(generated.data, null, 2) }],
      };
    }
    throw new Error("Either report_id or simulation_id must be provided");
  }
);

// Tool: chat_with_report
server.tool(
  "chat_with_report",
  "Chat with a MiroFish report agent. Ask follow-up questions about simulation findings, request deeper analysis, or interview specific simulated agents.",
  {
    report_id: z.string().describe("The report ID to chat with"),
    message: z.string().describe("Your question or request for the report agent"),
  },
  async ({ report_id, message }) => {
    const result = await apiCall("POST", `/api/report/${report_id}/chat`, { message });
    return {
      content: [{ type: "text", text: result.data?.response || JSON.stringify(result.data, null, 2) }],
    };
  }
);

// Tool: inject_variable
server.tool(
  "inject_variable",
  "Fork an existing simulation with modified parameters to create a 'what if' scenario. Creates a new simulation based on an existing one with changed variables.",
  {
    simulation_id: z.string().describe("The source simulation ID to fork"),
    requirement: z.string().optional().describe("Modified requirement/prompt for the forked simulation"),
    max_rounds: z.number().optional().describe("Different number of rounds"),
    variable_overrides: z.record(z.string()).optional().describe("Key-value pairs of variables to change"),
  },
  async ({ simulation_id, requirement, max_rounds, variable_overrides }) => {
    const body = {
      simulation_id,
      changes: {},
    };
    if (requirement) body.changes.requirement = requirement;
    if (max_rounds) body.changes.max_rounds = max_rounds;
    if (variable_overrides) body.changes.variable_overrides = variable_overrides;

    const result = await apiCall("POST", "/api/simulation/fork", body);
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

// Tool: get_simulation_status
server.tool(
  "get_simulation_status",
  "Check the current status of a running MiroFish simulation, including progress, round count, and agent activity.",
  {
    simulation_id: z.string().describe("The simulation ID to check"),
  },
  async ({ simulation_id }) => {
    const status = await apiCall("GET", `/api/simulation/${simulation_id}/run-status`);
    return {
      content: [{ type: "text", text: JSON.stringify(status.data, null, 2) }],
    };
  }
);

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
