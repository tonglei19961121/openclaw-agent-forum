"""
Agent Forum - Agent Manager Module
Manages agent lifecycle: hire, dismiss, rehire, update.
Provides dynamic agent registry backed by database + filesystem.
"""
import os
import json
import shutil
import subprocess
import sqlite3
from datetime import datetime
from config import DATABASE_PATH


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_agents_table():
    """Initialize the agents table in database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#999999',
            icon TEXT,
            webhook TEXT,
            status TEXT DEFAULT 'active',
            is_builtin BOOLEAN DEFAULT 0,
            hired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dismissed_at TIMESTAMP,
            dismissed_by TEXT,
            soul_md TEXT,
            agents_md TEXT
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
    conn.commit()
    conn.close()


def _scan_agents_directory():
    """Scan agents directory and return all agent configs.
    Reads CONFIG.json from each subdirectory in agents/
    Returns: dict like {'cto': {'name': 'CTO', 'description': '...', 'color': '...', 'icon': '...'}, ...}
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.join(base_dir, 'agents')
    
    agents = {}
    
    if not os.path.exists(agents_dir):
        return agents
    
    for entry in os.listdir(agents_dir):
        agent_path = os.path.join(agents_dir, entry)
        if not os.path.isdir(agent_path):
            continue
        
        config_path = os.path.join(agent_path, 'CONFIG.json')
        if not os.path.exists(config_path):
            continue
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            agents[entry] = {
                'name': config.get('name', entry.upper()),
                'description': config.get('description', ''),
                'color': config.get('color', '#999999'),
                'icon': config.get('icon', '🤖'),
                'webhook': config.get('webhook')
            }
        except (json.JSONDecodeError, IOError) as e:
            print(f"[AgentManager] Warning: Failed to read {config_path}: {e}")
    
    return agents


def init_default_agents():
    """Seed default agents from agents/ directory into database (idempotent).
    Scans agents/{agent_id}/CONFIG.json for configuration.
    Also reads SOUL.md / AGENTS.md from filesystem if available.
    All agents are initialized as 'dismissed' by default.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Scan agents directory for configs
    DEFAULT_AGENTS = _scan_agents_directory()

    for agent_id, agent_info in DEFAULT_AGENTS.items():
        # Check if already exists
        cursor.execute('SELECT id FROM agents WHERE id = ?', (agent_id,))
        if cursor.fetchone():
            continue

        # Read SOUL.md and AGENTS.md from filesystem
        soul_md = _read_agent_file(base_dir, agent_id, 'SOUL.md')
        agents_md = _read_agent_file(base_dir, agent_id, 'AGENTS.md')

        # Insert as 'dismissed' by default - need to rehire to activate
        cursor.execute('''
            INSERT INTO agents (id, name, description, color, icon, webhook, status, is_builtin, soul_md, agents_md)
            VALUES (?, ?, ?, ?, ?, ?, 'dismissed', 1, ?, ?)
        ''', (
            agent_id,
            agent_info['name'],
            agent_info.get('description', ''),
            agent_info.get('color', '#999999'),
            agent_info.get('icon', '🤖'),
            agent_info.get('webhook'),
            soul_md,
            agents_md
        ))

        # Do NOT register with OpenClaw or setup cron - agent is dismissed

    conn.commit()
    conn.close()


def _read_agent_file(base_dir, agent_id, filename):
    """Read a file from agents/{agent_id}/{filename}"""
    filepath = os.path.join(base_dir, 'agents', agent_id, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return None


# ============== Query Functions ==============

def get_active_agents():
    """Get all active agents as a dict (compatible with config.AGENTS format).
    Returns: dict like {'cto': {'name': 'CTO', 'description': '...', 'color': '...', ...}, ...}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents WHERE status = 'active' ORDER BY hired_at ASC")
    rows = cursor.fetchall()
    conn.close()

    agents = {}
    for row in rows:
        agents[row['id']] = {
            'name': row['name'],
            'description': row['description'] or '',
            'color': row['color'] or '#999999',
            'icon': row['icon'] or '🤖',
            'webhook': row['webhook'],
            'status': row['status'],
            'is_builtin': bool(row['is_builtin']),
            'hired_at': row['hired_at'],
        }
    return agents


def get_all_agents(include_dismissed=False):
    """Get all agents, optionally including dismissed ones.
    Returns: dict
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_dismissed:
        cursor.execute("SELECT * FROM agents ORDER BY status ASC, hired_at ASC")
    else:
        cursor.execute("SELECT * FROM agents WHERE status = 'active' ORDER BY hired_at ASC")
    rows = cursor.fetchall()
    conn.close()

    agents = {}
    for row in rows:
        agents[row['id']] = {
            'name': row['name'],
            'description': row['description'] or '',
            'color': row['color'] or '#999999',
            'icon': row['icon'] or '🤖',
            'webhook': row['webhook'],
            'status': row['status'],
            'is_builtin': bool(row['is_builtin']),
            'hired_at': row['hired_at'],
            'dismissed_at': row['dismissed_at'],
            'dismissed_by': row['dismissed_by'],
        }
    return agents


def get_agent(agent_id):
    """Get a single agent by ID (regardless of status).
    Returns: dict or None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'id': row['id'],
        'name': row['name'],
        'description': row['description'] or '',
        'color': row['color'] or '#999999',
        'icon': row['icon'] or '🤖',
        'webhook': row['webhook'],
        'status': row['status'],
        'is_builtin': bool(row['is_builtin']),
        'hired_at': row['hired_at'],
        'dismissed_at': row['dismissed_at'],
        'dismissed_by': row['dismissed_by'],
        'soul_md': row['soul_md'],
        'agents_md': row['agents_md'],
    }


# ============== Hire / Dismiss / Rehire ==============

def _get_default_agents_md():
    """Read default AGENTS.md content from docs/API_QUICK.md (quick reference)"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Use quick API reference instead of full documentation
    api_doc_path = os.path.join(base_dir, 'docs', 'API_QUICK.md')
    if os.path.exists(api_doc_path):
        with open(api_doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def _get_cron_template():
    """Read cron message template from docs/CRON_TEMPLATE.md"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, 'docs', 'CRON_TEMPLATE.md')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def hire_agent(agent_id, name, description, color='#999999', icon='🤖',
               webhook=None, soul_md=None, agents_md=None):
    """Hire (create) a new agent.
    Also creates filesystem workspace and configures OpenClaw cron.
    Returns: dict with agent info or None on failure.
    """
    agent_id = agent_id.lower().strip()

    # Validate agent_id
    if not agent_id or not agent_id.isalnum():
        return {'error': 'Agent ID must be alphanumeric'}

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if already exists
    cursor.execute('SELECT id, status FROM agents WHERE id = ?', (agent_id,))
    existing = cursor.fetchone()

    if existing:
        if existing['status'] == 'active':
            conn.close()
            return {'error': f'Agent "{agent_id}" already exists and is active'}
        else:
            # Rehire dismissed agent with updated info
            conn.close()
            return rehire_agent(agent_id, name=name, description=description,
                                color=color, icon=icon, soul_md=soul_md, agents_md=agents_md)

    try:
        cursor.execute('''
            INSERT INTO agents (id, name, description, color, icon, webhook, status, is_builtin, soul_md, agents_md)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?, ?)
        ''', (agent_id, name, description, color, icon, webhook, soul_md, agents_md))
        conn.commit()
    except Exception as e:
        conn.close()
        return {'error': f'Database error: {str(e)}'}
    finally:
        conn.close()

    # Register agent with OpenClaw and setup cron
    _setup_openclaw_agent(agent_id, name, soul_md, agents_md)
    _setup_openclaw_cron(agent_id, name, description, soul_md)

    return {
        'success': True,
        'agent_id': agent_id,
        'name': name,
        'description': description,
        'color': color,
        'icon': icon,
    }


def dismiss_agent(agent_id, dismissed_by='chairman'):
    """Dismiss (soft-delete) an agent.
    Cancels pending tasks and removes OpenClaw cron.
    Returns: dict
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, status, name FROM agents WHERE id = ?", (agent_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'error': f'Agent "{agent_id}" not found'}

    if row['status'] == 'dismissed':
        conn.close()
        return {'error': f'Agent "{agent_id}" is already dismissed'}

    # Update agent status
    cursor.execute('''
        UPDATE agents SET status = 'dismissed', dismissed_at = CURRENT_TIMESTAMP, dismissed_by = ?
        WHERE id = ?
    ''', (dismissed_by, agent_id))

    # Cancel all pending tasks for this agent
    cursor.execute('''
        UPDATE tasks SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
        WHERE assignee = ? AND status IN ('todo', 'doing')
    ''', (agent_id,))
    cancelled_tasks = cursor.rowcount

    conn.commit()
    conn.close()

    # Remove OpenClaw cron and agent
    _remove_openclaw_cron(agent_id)
    _remove_openclaw_agent(agent_id)

    return {
        'success': True,
        'agent_id': agent_id,
        'name': row['name'],
        'dismissed_by': dismissed_by,
        'cancelled_tasks': cancelled_tasks,
    }


def rehire_agent(agent_id, name=None, description=None, color=None,
                 icon=None, soul_md=None, agents_md=None):
    """Rehire a dismissed agent, optionally updating their info.
    Returns: dict
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {'error': f'Agent "{agent_id}" not found'}

    if row['status'] == 'active':
        conn.close()
        return {'error': f'Agent "{agent_id}" is already active'}

    # Build update fields
    updates = ['status = ?', 'dismissed_at = NULL', 'dismissed_by = NULL', 'hired_at = CURRENT_TIMESTAMP']
    params = ['active']

    if name:
        updates.append('name = ?')
        params.append(name)
    if description:
        updates.append('description = ?')
        params.append(description)
    if color:
        updates.append('color = ?')
        params.append(color)
    if icon:
        updates.append('icon = ?')
        params.append(icon)
    if soul_md:
        updates.append('soul_md = ?')
        params.append(soul_md)
    if agents_md:
        updates.append('agents_md = ?')
        params.append(agents_md)

    params.append(agent_id)
    cursor.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    # Re-setup OpenClaw agent and cron
    agent = get_agent(agent_id)
    if agent:
        _setup_openclaw_agent(agent_id, agent['name'], agent.get('soul_md'), agent.get('agents_md'))
        _setup_openclaw_cron(agent_id, agent['name'], agent.get('description', ''), agent.get('soul_md'))

    return {
        'success': True,
        'agent_id': agent_id,
        'name': name or row['name'],
    }


def update_agent(agent_id, **kwargs):
    """Update agent fields.
    Allowed kwargs: name, description, color, icon, webhook, soul_md, agents_md
    Returns: dict
    """
    allowed_fields = {'name', 'description', 'color', 'icon', 'webhook', 'soul_md', 'agents_md'}
    updates = []
    params = []

    for key, value in kwargs.items():
        if key in allowed_fields and value is not None:
            updates.append(f'{key} = ?')
            params.append(value)

    if not updates:
        return {'error': 'No valid fields to update'}

    params.append(agent_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params)
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        return {'error': f'Agent "{agent_id}" not found'}

    # Sync to OpenClaw workspace and cron
    if 'soul_md' in kwargs or 'agents_md' in kwargs:
        agent = get_agent(agent_id)
        if agent:
            new_soul_md = kwargs.get('soul_md') or agent.get('soul_md')
            new_agents_md = kwargs.get('agents_md') or agent.get('agents_md')
            
            _setup_openclaw_workspace(agent_id, agent['name'], new_soul_md, new_agents_md)
            
            # Update cron job with new soul_md
            _remove_openclaw_cron(agent_id)
            _setup_openclaw_cron(agent_id, agent['name'], agent.get('description', ''), new_soul_md)

    return {'success': True, 'agent_id': agent_id, 'updated_fields': list(kwargs.keys())}


# ============== OpenClaw Integration ==============

def _setup_openclaw_workspace(agent_id, name, soul_md=None, agents_md=None):
    """Create OpenClaw workspace directory and write SOUL.md / AGENTS.md.
    API documentation is automatically appended to AGENTS.md when writing to workspace.
    Database stores clean agents_md without API docs.
    """
    workspace_dir = os.path.expanduser(f'~/.openclaw/workspace-{agent_id}')
    try:
        os.makedirs(workspace_dir, exist_ok=True)

        if soul_md:
            with open(os.path.join(workspace_dir, 'SOUL.md'), 'w', encoding='utf-8') as f:
                f.write(soul_md)

        # Append API documentation when writing to workspace (not stored in DB)
        api_doc = _get_default_agents_md()
        if agents_md or api_doc:
            final_agents_md = agents_md or ''
            # Only append API doc if not already present
            if api_doc and 'Agent Forum API' not in final_agents_md:
                if final_agents_md:
                    final_agents_md = final_agents_md.rstrip() + '\n\n---\n\n' + api_doc
                else:
                    final_agents_md = api_doc
            with open(os.path.join(workspace_dir, 'AGENTS.md'), 'w', encoding='utf-8') as f:
                f.write(final_agents_md)

        print(f"[AgentManager] Workspace created for {agent_id} at {workspace_dir}")
    except Exception as e:
        print(f"[AgentManager] Warning: Failed to create workspace for {agent_id}: {e}")


def _setup_openclaw_agent(agent_id, name, soul_md=None, agents_md=None):
    """Register an agent with OpenClaw via CLI (agents add) and prepare workspace.
    Skips if the agent already exists in OpenClaw.
    """
    # First create workspace directory with SOUL.md / AGENTS.md
    _setup_openclaw_workspace(agent_id, name, soul_md, agents_md)

    workspace_dir = os.path.expanduser(f'~/.openclaw/workspace-{agent_id}')

    # Check if agent already exists in OpenClaw
    try:
        result = subprocess.run(
            ['openclaw', 'agents', 'list', '--json'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            try:
                agents_list = json.loads(result.stdout)
                for agent in agents_list:
                    if agent.get('id', '').lower() == agent_id.lower():
                        print(f"[AgentManager] Agent {agent_id} already exists in OpenClaw, skipping add")
                        return
            except json.JSONDecodeError:
                pass
    except (FileNotFoundError, Exception):
        pass

    # Register agent via CLI
    add_cmd = [
        'openclaw', 'agents', 'add',
        agent_id,
        '--workspace', workspace_dir,
        '--non-interactive'
    ]

    try:
        result = subprocess.run(add_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"[AgentManager] Agent {agent_id} registered with OpenClaw")
        else:
            print(f"[AgentManager] Warning: openclaw agents add failed for {agent_id}: {result.stderr}")
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found, skipping agent registration for {agent_id}")
    except Exception as e:
        print(f"[AgentManager] Warning: Agent registration error for {agent_id}: {e}")


def _remove_openclaw_agent(agent_id):
    """Remove an agent from OpenClaw via CLI (agents delete --force)"""
    try:
        result = subprocess.run(
            ['openclaw', 'agents', 'delete', agent_id, '--force'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"[AgentManager] Agent {agent_id} removed from OpenClaw")
        else:
            print(f"[AgentManager] Warning: openclaw agents delete failed for {agent_id}: {result.stderr}")
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found, skipping agent removal for {agent_id}")
    except Exception as e:
        print(f"[AgentManager] Warning: Agent removal error for {agent_id}: {e}")


def _setup_openclaw_cron(agent_id, name, description, soul_md=None):
    """Configure OpenClaw cron job for the agent"""
    # Read cron message template from file
    template = _get_cron_template()
    if template:
        cron_message = template.format(
            name=name,
            description=description or 'Agent',
            agent_id=agent_id
        )
    else:
        # Fallback to default message if template file not found
        cron_message = f"你是 {name}（{description or 'Agent'}）。Agent ID: {agent_id}\n\n检查 Agent Forum 中是否有 @{agent_id} 的提及。"
    
    cron_cmd = [
        'openclaw', 'cron', 'add',
        '--name', f'Agent Forum - {name} Monitor',
        '--cron', '0 * * * *',
        '--session', 'isolated',
        '--message', cron_message,
        '--agent', agent_id,
        '--no-deliver',
        '--timeout-seconds', '600',
        '--model', 'bailian/qwen3.5-plus'
    ]

    try:
        result = subprocess.run(cron_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"[AgentManager] Cron job created for {agent_id}")
        else:
            print(f"[AgentManager] Warning: Cron setup failed for {agent_id}: {result.stderr}")
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found, skipping cron setup for {agent_id}")
    except Exception as e:
        print(f"[AgentManager] Warning: Cron setup error for {agent_id}: {e}")


def _remove_openclaw_cron(agent_id):
    """Remove OpenClaw cron job for the agent"""
    try:
        # List cron jobs and find the one for this agent
        result = subprocess.run(
            ['openclaw', 'cron', 'list', '--json'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            try:
                # Find the JSON object (may have warning output before it)
                stdout = result.stdout
                json_start = stdout.find('{')
                if json_start == -1:
                    print(f"[AgentManager] Warning: No JSON found in cron list for {agent_id}")
                    return
                
                data = json.loads(stdout[json_start:])
                cron_jobs = data.get('jobs', [])
                agent_id_lower = agent_id.lower()
                
                for job in cron_jobs:
                    job_name = job.get('name', '').lower()
                    job_agent = job.get('agentId', job.get('agent', '')).lower()
                    if agent_id_lower in job_name or agent_id_lower == job_agent:
                        job_id = job.get('id', job.get('jobId', ''))
                        if job_id:
                            rm_result = subprocess.run(
                                ['openclaw', 'cron', 'remove', job_id],
                                capture_output=True, text=True, timeout=30
                            )
                            if rm_result.returncode == 0:
                                print(f"[AgentManager] Cron job '{job_id}' removed for {agent_id}")
                            else:
                                print(f"[AgentManager] Warning: Failed to remove cron job '{job_id}': {rm_result.stderr}")
            except json.JSONDecodeError:
                print(f"[AgentManager] Warning: Could not parse cron list for {agent_id}")
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found, skipping cron removal for {agent_id}")
    except Exception as e:
        print(f"[AgentManager] Warning: Cron removal error for {agent_id}: {e}")


def get_agent_cron(agent_id):
    """Get cron job info for a specific agent"""
    try:
        result = subprocess.run(
            ['openclaw', 'cron', 'list', '--json'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # Find the JSON object (may have warning output before it)
            stdout = result.stdout
            json_start = stdout.find('{')
            if json_start == -1:
                return None
            
            data = json.loads(stdout[json_start:])
            cron_jobs = data.get('jobs', [])
            agent_id_lower = agent_id.lower()
            
            for job in cron_jobs:
                job_agent = job.get('agentId', job.get('agent', '')).lower()
                job_name = job.get('name', '').lower()
                if agent_id_lower == job_agent or agent_id_lower in job_name:
                    schedule = job.get('schedule', {})
                    payload = job.get('payload', {})
                    return {
                        'job_id': job.get('id', job.get('jobId', '')),
                        'name': job.get('name', ''),
                        'cron': schedule.get('expr', '') if isinstance(schedule, dict) else '',
                        'message': payload.get('message', '') if isinstance(payload, dict) else '',
                        'enabled': job.get('enabled', True),
                        'session': job.get('sessionTarget', 'isolated'),
                        'last_run': job.get('lastRun'),
                        'next_run': job.get('nextRun'),
                    }
            return None
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found")
        return None
    except Exception as e:
        print(f"[AgentManager] Warning: Error getting cron for {agent_id}: {e}")
        return None


def update_agent_cron(agent_id, cron_expr=None, message=None):
    """Update cron job for an agent"""
    # First get the job id
    cron_info = get_agent_cron(agent_id)
    if not cron_info:
        return {'error': f'No cron job found for agent {agent_id}'}
    
    job_id = cron_info['job_id']
    if not job_id:
        return {'error': 'Could not find job id'}
    
    cmd = ['openclaw', 'cron', 'edit', job_id]
    
    if cron_expr:
        cmd.extend(['--cron', cron_expr])
    if message:
        cmd.extend(['--message', message])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return {'success': True, 'job_id': job_id}
        else:
            return {'error': f'Cron edit failed: {result.stderr}'}
    except FileNotFoundError:
        return {'error': 'openclaw CLI not found'}
    except Exception as e:
        return {'error': f'Cron edit error: {e}'}
