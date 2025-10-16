/* ── 1.  Create logical roles ─────────────────────────────────────────────── */
CREATE ROLE customer_role;
CREATE ROLE agent_role;
CREATE ROLE staff_operator_role;   -- can update flight status
CREATE ROLE staff_admin_role;      -- full airline-maintenance powers

/* ── 2.  Grant table-level privileges to each role ────────────────────────── */
/* Customers – read-only on public data, nothing else                         */
GRANT SELECT ON ticket_reserve_system.Flight   TO customer_role;
GRANT SELECT ON ticket_reserve_system.Airport  TO customer_role;

/* Booking Agents – can buy tickets (insert Ticket & purchases rows)          */
GRANT SELECT ON ticket_reserve_system.*        TO agent_role;
GRANT INSERT ON ticket_reserve_system.Ticket   TO agent_role;
GRANT INSERT ON ticket_reserve_system.purchases TO agent_role;

/* Staff Operators – may update flight status, but not create resources       */
GRANT SELECT, UPDATE (flight_status)
      ON ticket_reserve_system.Flight          TO staff_operator_role;

/* Staff Admins – full control of airline data                                */
GRANT SELECT                                 ON ticket_reserve_system.* TO staff_admin_role;
GRANT INSERT, UPDATE, DELETE                 ON ticket_reserve_system.Flight   TO staff_admin_role;
GRANT INSERT, UPDATE, DELETE                 ON ticket_reserve_system.Airplane TO staff_admin_role;
GRANT INSERT, UPDATE, DELETE                 ON ticket_reserve_system.Airport  TO staff_admin_role;
GRANT INSERT, UPDATE, DELETE                 ON ticket_reserve_system.Permission_status TO staff_admin_role;
GRANT INSERT, UPDATE, DELETE                 ON ticket_reserve_system.Agent_status      TO staff_admin_role;

/* ── 3.  Bind application accounts to those roles (examples) ─────────────── */
CREATE USER 'cust_app'@'%' IDENTIFIED BY 'custpwd';
CREATE USER 'agent_app'@'%' IDENTIFIED BY 'agentpwd';
CREATE USER 'staff_app'@'%' IDENTIFIED BY 'staffpwd';

GRANT customer_role        TO 'cust_app'@'%';
GRANT agent_role           TO 'agent_app'@'%';
GRANT staff_admin_role     TO 'staff_app'@'%';  -- could be operator if you prefer

/* Make the granted role the default role for each account                    */
SET DEFAULT ROLE ALL TO 'cust_app'@'%', 'agent_app'@'%', 'staff_app'@'%';