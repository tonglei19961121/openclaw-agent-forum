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
from config import DATABASE_PATH, AGENTS as DEFAULT_AGENTS


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


def init_default_agents():
    """Seed default agents from config.py into database (idempotent).
    Also reads SOUL.md / AGENTS.md from filesystem if available.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    for agent_id, agent_info in DEFAULT_AGENTS.items():
        # Check if already exists
        cursor.execute('SELECT id FROM agents WHERE id = ?', (agent_id,))
        if cursor.fetchone():
            continue

        # Read SOUL.md and AGENTS.md from filesystem
        soul_md = _read_agent_file(base_dir, agent_id, 'SOUL.md')
        agents_md = _read_agent_file(base_dir, agent_id, 'AGENTS.md')

        # Default icons for builtin agents
        default_icons = {
            'ceo': '👑', 'cto': '⚙️', 'cmo': '📢',
            'pm': '📋', 'lucy': '🐱'
        }

        cursor.execute('''
            INSERT INTO agents (id, name, description, color, icon, webhook, status, is_builtin, soul_md, agents_md)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?)
        ''', (
            agent_id,
            agent_info['name'],
            agent_info.get('description', ''),
            agent_info.get('color', '#999999'),
            default_icons.get(agent_id, '🤖'),
            agent_info.get('webhook'),
            soul_md,
            agents_md
        ))

    conn.commit()
    conn.close()


def _read_agent_file(base_dir, agent_id, filename):
    """Read a file from agents/{agent_id}/{filename}"""
    filepath = os.path.join(base_dir, 'agents', agent_id, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def _write_agent_file(base_dir, agent_id, filename, content):
    """Write content to agents/{agent_id}/{filename}"""
    agent_dir = os.path.join(base_dir, 'agents', agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    filepath = os.path.join(agent_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


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

    # Write to filesystem (Plan C: both DB and filesystem)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if soul_md:
        _write_agent_file(base_dir, agent_id, 'SOUL.md', soul_md)
    if agents_md:
        _write_agent_file(base_dir, agent_id, 'AGENTS.md', agents_md)

    # Create memory directory
    memory_dir = os.path.join(base_dir, 'agents', agent_id, 'memory')
    os.makedirs(memory_dir, exist_ok=True)
    context_path = os.path.join(memory_dir, 'context.md')
    if not os.path.exists(context_path):
        with open(context_path, 'w', encoding='utf-8') as f:
            f.write(f'# {name} Context\n\nNo context yet.\n')

    # Setup OpenClaw workspace and cron
    _setup_openclaw_workspace(agent_id, name, soul_md, agents_md)
    _setup_openclaw_cron(agent_id, name, description)

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

    # Remove OpenClaw cron
    _remove_openclaw_cron(agent_id)

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

    # Update filesystem (Plan C)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if soul_md:
        _write_agent_file(base_dir, agent_id, 'SOUL.md', soul_md)
    if agents_md:
        _write_agent_file(base_dir, agent_id, 'AGENTS.md', agents_md)

    # Re-setup OpenClaw
    agent = get_agent(agent_id)
    if agent:
        _setup_openclaw_workspace(agent_id, agent['name'], agent.get('soul_md'), agent.get('agents_md'))
        _setup_openclaw_cron(agent_id, agent['name'], agent.get('description', ''))

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

    # Sync filesystem (Plan C)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if 'soul_md' in kwargs and kwargs['soul_md']:
        _write_agent_file(base_dir, agent_id, 'SOUL.md', kwargs['soul_md'])
    if 'agents_md' in kwargs and kwargs['agents_md']:
        _write_agent_file(base_dir, agent_id, 'AGENTS.md', kwargs['agents_md'])

    return {'success': True, 'agent_id': agent_id, 'updated_fields': list(kwargs.keys())}


# ============== OpenClaw Integration ==============

def _setup_openclaw_workspace(agent_id, name, soul_md=None, agents_md=None):
    """Create OpenClaw workspace for the agent"""
    workspace_dir = os.path.expanduser(f'~/.openclaw/workspace-{agent_id}')
    try:
        os.makedirs(workspace_dir, exist_ok=True)

        if soul_md:
            with open(os.path.join(workspace_dir, 'SOUL.md'), 'w', encoding='utf-8') as f:
                f.write(soul_md)

        if agents_md:
            with open(os.path.join(workspace_dir, 'AGENTS.md'), 'w', encoding='utf-8') as f:
                f.write(agents_md)

        print(f"[AgentManager] Workspace created for {agent_id} at {workspace_dir}")
    except Exception as e:
        print(f"[AgentManager] Warning: Failed to create workspace for {agent_id}: {e}")


def _setup_openclaw_cron(agent_id, name, description):
    """Configure OpenClaw cron job for the agent"""
    cron_message = (
        f"你是 {name} Agent。检查 Agent Forum (http://localhost:5000) 中是否有 @{agent_id} 的提及。"
        f"如果有，阅读帖子内容，从{description}的角度给出专业建议。"
    )
    cron_cmd = [
        'openclaw', 'cron', 'add',
        '--name', f'Agent Forum - {name} Monitor',
        '--cron', '*/2 * * * *',
        '--session', 'isolated',
        '--message', cron_message,
        '--agent', agent_id,
        '--delivery', 'none',
        '--exact'
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
                cron_jobs = json.loads(result.stdout)
                for job in cron_jobs:
                    if agent_id in job.get('name', '').lower() or agent_id in job.get('agent', '').lower():
                        subprocess.run(
                            ['openclaw', 'cron', 'remove', '--name', job['name']],
                            capture_output=True, text=True, timeout=30
                        )
                        print(f"[AgentManager] Cron job removed for {agent_id}")
            except json.JSONDecodeError:
                print(f"[AgentManager] Warning: Could not parse cron list for {agent_id}")
    except FileNotFoundError:
        print(f"[AgentManager] Warning: openclaw CLI not found, skipping cron removal for {agent_id}")
    except Exception as e:
        print(f"[AgentManager] Warning: Cron removal error for {agent_id}: {e}")
