# Planitt Admin Test Plan

## Smoke checks

Run:

```bash
npm run lint
npm run typecheck
npm run smoke
```

## Manual e2e checklist

1. Login flow
   - Open `/login`
   - Submit invalid credentials -> error shown
   - Submit valid credentials -> redirected to `/dashboard`

2. Route protection
   - Open `/dashboard/signals` in a new incognito window
   - Expect redirect to `/login`

3. Signals console
   - Verify table loads from `/api/admin/signals`
   - Apply filters and pagination
   - Select row -> details panel updates

4. Generation controls
   - Trigger manual generation
   - Confirm request succeeds/fails with visible feedback

5. News and ops
   - News page loads sentiment feed
   - Ops page shows health tiles and market status payload

6. Logout
   - Click Logout
   - Confirm redirection to `/login`

