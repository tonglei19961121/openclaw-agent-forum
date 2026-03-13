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
            agents_md TEXT,
            openclaw_agent_created BOOLEAN DEFAULT 0,
            openclaw_cron_id TEXT,
            openclaw_sync_status TEXT DEFAULT 'pending',
            openclaw_sync_error TEXT,
            openclaw_sync_at TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_sync_status ON agents(openclaw_sync_status)')
    
    # 为已存在的表添加新字段（兼容旧数据）
    try:
        cursor.execute('ALTER TABLE agents ADD COLUMN openclaw_agent_created BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE agents ADD COLUMN openclaw_cron_id TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE agents ADD COLUMN openclaw_sync_status TEXT DEFAULT "pending"')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE agents ADD COLUMN openclaw_sync_error TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE agents ADD COLUMN openclaw_sync_at TIMESTAMP')
    except sqlite3.OperationalError:
        pass
    
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
        'openclaw_agent_created': bool(row['openclaw_agent_created']) if 'openclaw_agent_created' in row.keys() else False,
        'openclaw_cron_id': row['openclaw_cron_id'] if 'openclaw_cron_id' in row.keys() else None,
        'openclaw_sync_status': row['openclaw_sync_status'] if 'openclaw_sync_status' in row.keys() else 'pending',
        'openclaw_sync_error': row['openclaw_sync_error'] if 'openclaw_sync_error' in row.keys() else None,
        'openclaw_sync_at': row['openclaw_sync_at'] if 'openclaw_sync_at' in row.keys() else None,
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


def _update_agent_sync_status(agent_id, sync_status, agent_created=None, cron_id=None, error=None):
    """Update agent's OpenClaw sync status in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = ['openclaw_sync_status = ?', 'openclaw_sync_at = CURRENT_TIMESTAMP']
    params = [sync_status]
    
    if agent_created is not None:
        updates.append('openclaw_agent_created = ?')
        params.append(1 if agent_created else 0)
    
    if cron_id is not None:
        updates.append('openclaw_cron_id = ?')
        params.append(cron_id)
    
    if error is not None:
        updates.append('openclaw_sync_error = ?')
        params.append(error)
    elif sync_status == 'synced':
        updates.append('openclaw_sync_error = NULL')
    
    params.append(agent_id)
    
    cursor.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def hire_agent(agent_id, name, description, color='#999999', icon='🤖',
               webhook=None, soul_md=None, agents_md=None):
    """Hire (create) a new agent.
    
    This function ensures atomicity:
    1. Creates database record with status='pending'
    2. Creates OpenClaw agent and cron
    3. Updates status to 'active' only if OpenClaw setup succeeds
    
    Returns: dict with agent info or error details.
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
    conn.close()

    # Step 1: Create database record with pending status
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO agents (id, name, description, color, icon, webhook, status, is_builtin, soul_md, agents_md,
                              openclaw_sync_status)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?, ?, 'pending')
        ''', (agent_id, name, description, color, icon, webhook, soul_md, agents_md))
        conn.commit()
    except Exception as e:
        conn.close()
        return {'error': f'Database error: {str(e)}'}
    finally:
        conn.close()

    # Step 2: Setup OpenClaw resources
    agent_result = _setup_openclaw_agent(agent_id, name, soul_md, agents_md)
    cron_result = _setup_openclaw_cron(agent_id, name, description, soul_md)
    
    # Step 3: Update sync status
    errors = []
    agent_created = agent_result['success']
    cron_created = cron_result['success']
    cron_id = cron_result.get('cron_id')
    
    if not agent_result['success']:
        errors.append(f"Agent: {agent_result['error']}")
    if not cron_result['success']:
        errors.append(f"Cron: {cron_result['error']}")
    
    if agent_created and cron_created:
        # All succeeded
        _update_agent_sync_status(agent_id, 'synced', agent_created=True, cron_id=cron_id)
        return {
            'success': True,
            'agent_id': agent_id,
            'name': name,
            'description': description,
            'color': color,
            'icon': icon,
            'openclaw_synced': True,
        }
    else:
        # Partial failure - record error but agent is still active in DB
        error_msg = '; '.join(errors)
        _update_agent_sync_status(agent_id, 'error', agent_created=agent_created, cron_id=cron_id, error=error_msg)
        return {
            'success': True,  # Agent created in DB
            'agent_id': agent_id,
            'name': name,
            'description': description,
            'color': color,
            'icon': icon,
            'openclaw_synced': False,
            'openclaw_errors': errors,
            'warning': f'Agent created but OpenClaw setup failed: {error_msg}',
        }


def dismiss_agent(agent_id, dismissed_by='chairman'):
    """Dismiss (soft-delete) an agent.
    
    This function ensures proper cleanup:
    1. Updates database status to 'dismissed'
    2. Removes OpenClaw cron and agent
    3. Updates sync status accordingly
    
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

    # Step 1: Update agent status
    cursor.execute('''
        UPDATE agents SET status = 'dismissed', dismissed_at = CURRENT_TIMESTAMP, dismissed_by = ?,
                          openclaw_sync_status = 'pending'
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

    # Step 2: Remove OpenClaw resources
    cron_result = _remove_openclaw_cron(agent_id)
    agent_result = _remove_openclaw_agent(agent_id)
    
    # Step 3: Update sync status
    errors = []
    if not cron_result['success']:
        errors.append(f"Cron removal: {cron_result['error']}")
    if not agent_result['success']:
        errors.append(f"Agent removal: {agent_result['error']}")
    
    if not errors:
        _update_agent_sync_status(agent_id, 'synced', agent_created=False, cron_id=None)
    else:
        error_msg = '; '.join(errors)
        _update_agent_sync_status(agent_id, 'error', error=error_msg)

    result = {
        'success': True,
        'agent_id': agent_id,
        'name': row['name'],
        'dismissed_by': dismissed_by,
        'cancelled_tasks': cancelled_tasks,
        'openclaw_cleaned': len(errors) == 0,
    }
    
    if errors:
        result['openclaw_errors'] = errors
        
    return result


def rehire_agent(agent_id, name=None, description=None, color=None,
                 icon=None, soul_md=None, agents_md=None):
    """Rehire a dismissed agent, optionally updating their info.
    
    This function ensures proper OpenClaw resource setup during rehire.
    
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

    # Build update fields - reset openclaw sync state on rehire
    updates = ['status = ?', 'dismissed_at = NULL', 'dismissed_by = NULL', 'hired_at = CURRENT_TIMESTAMP',
               'openclaw_sync_status = ?', 'openclaw_agent_created = 0', 'openclaw_cron_id = NULL', 'openclaw_sync_error = NULL']
    params = ['active', 'pending']

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
        agent_result = _setup_openclaw_agent(agent_id, agent['name'], agent.get('soul_md'), agent.get('agents_md'))
        cron_result = _setup_openclaw_cron(agent_id, agent['name'], agent.get('description', ''), agent.get('soul_md'))
        
        # Update sync status
        errors = []
        agent_created = agent_result['success']
        cron_id = cron_result.get('cron_id')
        
        if not agent_result['success']:
            errors.append(f"Agent: {agent_result['error']}")
        if not cron_result['success']:
            errors.append(f"Cron: {cron_result['error']}")
        
        if agent_created and cron_result['success']:
            _update_agent_sync_status(agent_id, 'synced', agent_created=True, cron_id=cron_id)
        else:
            error_msg = '; '.join(errors)
            _update_agent_sync_status(agent_id, 'error', agent_created=agent_created, cron_id=cron_id, error=error_msg)
        
        result = {
            'success': True,
            'agent_id': agent_id,
            'name': name or row['name'],
            'openclaw_synced': len(errors) == 0,
        }
        if errors:
            result['openclaw_errors'] = errors
        return result

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
    
    Returns: dict with {'success': bool, 'error': str or None}
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
                        return {'success': True, 'error': None}
            except json.JSONDecodeError:
                pass
    except (FileNotFoundError, Exception) as e:
        return {'success': False, 'error': f'Failed to check existing agents: {str(e)}'}

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
            return {'success': True, 'error': None}
        else:
            error_msg = result.stderr.strip() or f'exit code {result.returncode}'
            print(f"[AgentManager] Warning: openclaw agents add failed for {agent_id}: {error_msg}")
            return {'success': False, 'error': error_msg}
    except FileNotFoundError:
        error_msg = 'openclaw CLI not found'
        print(f"[AgentManager] Warning: {error_msg}, skipping agent registration for {agent_id}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[AgentManager] Warning: Agent registration error for {agent_id}: {e}")
        return {'success': False, 'error': error_msg}


def _remove_openclaw_agent(agent_id):
    """Remove an agent from OpenClaw via CLI (agents delete --force)
    
    Returns: dict with {'success': bool, 'error': str or None}
    """
    try:
        result = subprocess.run(
            ['openclaw', 'agents', 'delete', agent_id, '--force'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"[AgentManager] Agent {agent_id} removed from OpenClaw")
            return {'success': True, 'error': None}
        else:
            error_msg = result.stderr.strip() or f'exit code {result.returncode}'
            print(f"[AgentManager] Warning: openclaw agents delete failed for {agent_id}: {error_msg}")
            return {'success': False, 'error': error_msg}
    except FileNotFoundError:
        error_msg = 'openclaw CLI not found'
        print(f"[AgentManager] Warning: {error_msg}, skipping agent removal for {agent_id}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[AgentManager] Warning: Agent removal error for {agent_id}: {e}")
        return {'success': False, 'error': error_msg}


def _setup_openclaw_cron(agent_id, name, description, soul_md=None):
    """Configure OpenClaw cron job for the agent
    
    Returns: dict with {'success': bool, 'cron_id': str or None, 'error': str or None}
    """
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
            # Try to extract cron_id from output or fetch it
            cron_id = _get_cron_id_for_agent(agent_id)
            return {'success': True, 'cron_id': cron_id, 'error': None}
        else:
            error_msg = result.stderr.strip() or f'exit code {result.returncode}'
            print(f"[AgentManager] Warning: Cron setup failed for {agent_id}: {error_msg}")
            return {'success': False, 'cron_id': None, 'error': error_msg}
    except FileNotFoundError:
        error_msg = 'openclaw CLI not found'
        print(f"[AgentManager] Warning: {error_msg}, skipping cron setup for {agent_id}")
        return {'success': False, 'cron_id': None, 'error': error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[AgentManager] Warning: Cron setup error for {agent_id}: {e}")
        return {'success': False, 'cron_id': None, 'error': error_msg}


def _get_cron_id_for_agent(agent_id):
    """Get cron job ID for a specific agent"""
    try:
        result = subprocess.run(
            ['openclaw', 'cron', 'list', '--json'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
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
                    return job.get('id', job.get('jobId', ''))
    except Exception:
        pass
    return None


def _remove_openclaw_cron(agent_id):
    """Remove OpenClaw cron job for the agent
    
    Returns: dict with {'success': bool, 'error': str or None}
    """
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
                    return {'success': True, 'error': None}  # No cron to remove
                
                data = json.loads(stdout[json_start:])
                cron_jobs = data.get('jobs', [])
                agent_id_lower = agent_id.lower()
                
                removed_any = False
                errors = []
                
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
                                removed_any = True
                            else:
                                error_msg = rm_result.stderr.strip() or f'exit code {rm_result.returncode}'
                                print(f"[AgentManager] Warning: Failed to remove cron job '{job_id}': {error_msg}")
                                errors.append(f"cron {job_id}: {error_msg}")
                
                if errors:
                    return {'success': False, 'error': '; '.join(errors)}
                return {'success': True, 'error': None}
            except json.JSONDecodeError as e:
                print(f"[AgentManager] Warning: Could not parse cron list for {agent_id}")
                return {'success': False, 'error': f'JSON parse error: {e}'}
        else:
            return {'success': True, 'error': None}  # No cron jobs found
    except FileNotFoundError:
        error_msg = 'openclaw CLI not found'
        print(f"[AgentManager] Warning: {error_msg}, skipping cron removal for {agent_id}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[AgentManager] Warning: Cron removal error for {agent_id}: {e}")
        return {'success': False, 'error': error_msg}


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


# ============== Cron Trigger ==============

def trigger_agent_cron(agent_id):
    """通过命令行触发指定 agent 的 cron 任务（异步执行，不等待结果）
    
    当帖子/回复中 @mention Agent 时，立即触发该 Agent 检查通知并响应。
    """
    try:
        # 先通过 agentId 查找 job ID
        result = subprocess.run(
            ['openclaw', 'cron', 'list', '--json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # 提取 JSON 部分（去掉可能的警告信息）
            output = result.stdout
            # 找到 JSON 开始的位置（第一个 {）
            json_start = output.find('{')
            if json_start != -1:
                output = output[json_start:]
            
            jobs = json.loads(output)
            job_id = None
            for job in jobs.get('jobs', []):
                if job.get('agentId') == agent_id:
                    job_id = job.get('id')
                    break
            
            if job_id:
                # 异步触发 cron 任务，不等待执行完成
                subprocess.Popen(
                    ['openclaw', 'cron', 'run', job_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print(f"[Cron] Triggered {agent_id} cron job ({job_id}) asynchronously")
            else:
                print(f"[Cron] No cron job found for agent {agent_id}")
        else:
            print(f"[Cron] Failed to list jobs: {result.stderr}")
    except Exception as e:
        # 失败不影响主流程，Agent 会被定时 cron 兜底
        print(f"[Cron] Error triggering {agent_id}: {e}")


# ============== Sync & Reconciliation ==============

def _check_openclaw_agent_exists(agent_id):
    """Check if an agent exists in OpenClaw.
    
    Returns: bool
    """
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
                        return True
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    return False


def sync_agent_status(agent_id):
    """Check and fix sync status for a single agent.
    
    This function verifies that an agent's OpenClaw resources match its database status:
    - Active agents should have: agent + cron in OpenClaw
    - Dismissed agents should have: no agent + no cron in OpenClaw
    
    If mismatch found, attempts to fix it.
    
    Returns: dict with sync result
    """
    agent = get_agent(agent_id)
    if not agent:
        return {'error': f'Agent "{agent_id}" not found'}
    
    status = agent['status']
    db_agent_created = agent.get('openclaw_agent_created', False)
    db_cron_id = agent.get('openclaw_cron_id')
    
    # Check actual OpenClaw state
    actual_agent_exists = _check_openclaw_agent_exists(agent_id)
    actual_cron_info = get_agent_cron(agent_id)
    actual_cron_id = actual_cron_info.get('job_id') if actual_cron_info else None
    
    errors = []
    fixes = []
    
    if status == 'active':
        # Active agent should have agent + cron
        if not actual_agent_exists:
            # Missing agent - try to create
            print(f"[Sync] Agent {agent_id}: missing in OpenClaw, creating...")
            result = _setup_openclaw_agent(agent_id, agent['name'], agent.get('soul_md'), agent.get('agents_md'))
            if result['success']:
                fixes.append('Created OpenClaw agent')
            else:
                errors.append(f"Failed to create agent: {result['error']}")
        
        if not actual_cron_id:
            # Missing cron - try to create
            print(f"[Sync] Agent {agent_id}: missing cron, creating...")
            result = _setup_openclaw_cron(agent_id, agent['name'], agent.get('description', ''), agent.get('soul_md'))
            if result['success']:
                fixes.append('Created OpenClaw cron')
                actual_cron_id = result.get('cron_id')
            else:
                errors.append(f"Failed to create cron: {result['error']}")
        
        # Update sync status
        if not errors:
            _update_agent_sync_status(agent_id, 'synced', agent_created=True, cron_id=actual_cron_id)
        else:
            _update_agent_sync_status(agent_id, 'error', agent_created=actual_agent_exists, 
                                      cron_id=actual_cron_id, error='; '.join(errors))
    
    elif status == 'dismissed':
        # Dismissed agent should NOT have agent + cron
        if actual_agent_exists:
            print(f"[Sync] Agent {agent_id}: unexpected agent in OpenClaw, removing...")
            result = _remove_openclaw_agent(agent_id)
            if result['success']:
                fixes.append('Removed OpenClaw agent')
            else:
                errors.append(f"Failed to remove agent: {result['error']}")
        
        if actual_cron_id:
            print(f"[Sync] Agent {agent_id}: unexpected cron in OpenClaw, removing...")
            result = _remove_openclaw_cron(agent_id)
            if result['success']:
                fixes.append('Removed OpenClaw cron')
            else:
                errors.append(f"Failed to remove cron: {result['error']}")
        
        # Update sync status
        if not errors:
            _update_agent_sync_status(agent_id, 'synced', agent_created=False, cron_id=None)
        else:
            _update_agent_sync_status(agent_id, 'error', error='; '.join(errors))
    
    return {
        'agent_id': agent_id,
        'status': status,
        'synced': len(errors) == 0,
        'errors': errors if errors else None,
        'fixes': fixes if fixes else None,
        'state': {
            'db_status': status,
            'db_agent_created': db_agent_created,
            'db_cron_id': db_cron_id,
            'actual_agent_exists': actual_agent_exists,
            'actual_cron_id': actual_cron_id,
        }
    }


def reconcile_all_agents():
    """Check and fix sync status for all agents.
    
    This is a bulk operation that:
    1. Iterates through all agents in database
    2. For each agent, verifies OpenClaw resources match database status
    3. Attempts to fix any mismatches
    
    Returns: dict with summary of reconciliation
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM agents")
    rows = cursor.fetchall()
    conn.close()
    
    results = {
        'total_agents': len(rows),
        'synced': 0,
        'fixed': 0,
        'errors': 0,
        'details': []
    }
    
    for row in rows:
        agent_id = row['id']
        sync_result = sync_agent_status(agent_id)
        
        if sync_result.get('synced'):
            if sync_result.get('fixes'):
                results['fixed'] += 1
            else:
                results['synced'] += 1
        else:
            results['errors'] += 1
        
        results['details'].append(sync_result)
    
    return results


def get_unsynced_agents():
    """Get agents with sync_status != 'synced'
    
    Returns: list of agent dicts
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents WHERE openclaw_sync_status != 'synced'")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
