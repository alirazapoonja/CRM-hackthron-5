# TaskFlow Pro - Product Documentation

## Getting Started

### Creating Your First Project

1. Click the "+ New Project" button in the top navigation
2. Enter a project name and description
3. Choose a template (Blank, Marketing Campaign, Software Launch, etc.)
4. Invite team members by entering their email addresses
5. Click "Create Project"

### Inviting Team Members

1. Go to Project Settings → Members
2. Click "Invite Members"
3. Enter email addresses (separate multiple with commas)
4. Choose their role: Member (full access) or Guest (limited access)
5. Click "Send Invites"

Team members will receive an email with a link to join the workspace.

## Task Management

### Creating Tasks

**Method 1: Quick Add**
- Press `Q` anywhere to open quick add
- Type task name and press Enter

**Method 2: From Project**
- Click "+ Add Task" in your project
- Fill in task details:
  - Title (required)
  - Description (supports markdown)
  - Assignee
  - Due date
  - Priority (Low, Medium, High, Urgent)
  - Tags

### Task Dependencies

To create a dependency:
1. Open a task
2. Go to the "Dependencies" tab
3. Click "Add Dependency"
4. Search for and select the task to depend on
5. Choose: "Waiting on" (blocked by) or "Blocking" (blocks others)

**Note:** Dependencies are only available on Pro and higher plans.

### Recurring Tasks

1. Open or create a task
2. Click the due date field
3. Select "Repeat"
4. Choose frequency: Daily, Weekly, Monthly, Yearly, or Custom
5. Set end condition: Never, After X occurrences, or On specific date

## Views & Visualization

### Kanban Board

- Default view for most projects
- Drag and drop tasks between columns
- Click column settings to customize statuses
- Use "Swimlanes" to group by assignee, priority, or tags

### Gantt Chart

**Available on Pro and Enterprise plans only**

1. Switch to Gantt view from the view selector
2. Tasks appear as horizontal bars showing duration
3. Drag bar edges to adjust dates
4. Draw dependency lines between tasks
5. Critical path is highlighted in red

### Calendar View

- See tasks on a monthly/weekly calendar
- Filter by assignee or tags
- Drag tasks to reschedule
- Click any day to see task details

## Collaboration Features

### Comments & Mentions

- Add comments to any task
- Use @mention to notify team members
- Attach files up to your plan's limit:
  - Free: 100MB per file
  - Pro: 2GB per file
  - Business/Enterprise: 5GB per file

### Activity Feed

View all project activity in real-time:
- Task created/updated/completed
- Comments added
- Members joined/left
- Files uploaded

Access via the "Activity" tab in any project.

## Reporting

### Burndown Charts

**Available on Pro and higher plans**

1. Go to Reports → Burndown
2. Select project and date range
3. View ideal vs actual progress
4. Export as PNG or CSV

### Team Workload

**Available on Business and higher plans**

1. Go to Reports → Workload
2. See tasks assigned per team member
3. Identify over/under-utilized team members
4. Filter by date range and project

### Time Tracking

**Available on all paid plans**

1. Open a task
2. Click the timer icon to start tracking
3. Click again to stop
4. View logged time in task details
5. Export time reports from Reports → Time

## Integrations

### Slack Integration

1. Go to Settings → Integrations
2. Find Slack and click "Connect"
3. Authorize TaskFlow Pro in Slack
4. Choose which projects to sync
5. Configure notification preferences

Once connected:
- Receive Slack notifications for task updates
- Create tasks from Slack messages
- Search TaskFlow tasks without leaving Slack

### GitHub Integration

1. Go to Settings → Integrations
2. Find GitHub and click "Connect"
3. Authorize access to your repositories
4. Link specific repos to projects

Features:
- Attach GitHub issues to TaskFlow tasks
- See commit history in task details
- Auto-complete tasks when PRs are merged

### Google Drive Integration

1. Go to Settings → Integrations
2. Find Google Drive and click "Connect"
3. Sign in to your Google account
4. Choose folders to sync

Attach Drive files directly to tasks without uploading.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Q | Quick add task |
| / | Search |
| G then H | Go to Home |
| G then P | Go to Projects |
| G then T | Go to Tasks |
| ? | Show all shortcuts |

## Troubleshooting

### "I can't see the Gantt chart option"

Gantt charts are only available on Pro and Enterprise plans. Check your current plan in Settings → Billing, or contact your admin to upgrade.

### "My team member didn't receive the invite"

1. Ask them to check spam/junk folder
2. Verify you entered the correct email
3. Try resending from Project Settings → Members
4. If still not received, they can join directly via the project link

### "File upload keeps failing"

Check your file size against plan limits:
- Free: 100MB
- Pro: 2GB
- Business/Enterprise: 5GB

Also verify file type is allowed (executables .exe and .bat are blocked for security).

### "Tasks aren't syncing with Slack"

1. Go to Settings → Integrations → Slack
2. Click "Reconnect"
3. Verify you've granted all permissions
4. Check that the correct channels are selected

## Account & Billing

### Changing Your Plan

1. Go to Settings → Billing
2. Click "Change Plan"
3. Select new plan and confirm
4. Prorated charges apply for mid-cycle upgrades

### Canceling Subscription

1. Go to Settings → Billing
2. Click "Cancel Subscription"
3. Choose reason (optional)
4. Confirm cancellation

Your workspace remains accessible until the end of the billing period.

### Exporting Your Data

1. Go to Settings → Export
2. Choose format: JSON or CSV
3. Select what to export: Tasks, Projects, or All
4. Click "Request Export"

Exports are emailed within 24 hours for large workspaces.

## Security

### Two-Factor Authentication (2FA)

1. Go to Settings → Security
2. Click "Enable 2FA"
3. Scan QR code with authenticator app
4. Enter verification code
5. Save backup codes in a secure location

### Single Sign-On (SSO)

**Available on Business and Enterprise plans**

Contact your admin to configure SSO with:
- Google Workspace
- Microsoft Azure AD
- Okta
- OneLogin

## API Documentation

**Available on Pro and higher plans**

Base URL: `https://api.taskflowpro.com/v1`

Authentication: Bearer token (generate in Settings → API)

### Key Endpoints

```
GET /projects          - List all projects
POST /projects         - Create project
GET /tasks             - List tasks
POST /tasks            - Create task
PUT /tasks/{id}        - Update task
DELETE /tasks/{id}     - Delete task
GET /users             - List team members
```

Rate limits: 1000 requests/hour for Pro, 5000/hour for Business, unlimited for Enterprise.

Full API docs: https://developers.taskflowpro.com
