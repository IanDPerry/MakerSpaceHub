-- ---------------------------------------------------------------------
-- Roles
-- Referenced by: Users.roleID
-- ---------------------------------------------------------------------
CREATE TABLE Roles (
    roleID      INT AUTO_INCREMENT PRIMARY KEY,
    roleName    VARCHAR(50) NOT NULL UNIQUE   -- e.g. 'student', 'staff', 'maintenance', 'admin'
);
-- ---------------------------------------------------------------------
-- Users
-- One Role -> Many Users (mandatory both sides): every user must have a role
-- ---------------------------------------------------------------------
CREATE TABLE Users (
    userID      INT AUTO_INCREMENT PRIMARY KEY,
    roleID      INT NOT NULL,
    firstName   VARCHAR(50)  NOT NULL,
    lastName    VARCHAR(50)  NOT NULL,
    email       VARCHAR(100) NOT NULL UNIQUE,
    address     VARCHAR(150),
    phoneNumber VARCHAR(20),
    CONSTRAINT fk_users_role
        FOREIGN KEY (roleID) REFERENCES Roles(roleID)
);
 
-- ---------------------------------------------------------------------
-- Accounts
-- One User -> One Account (mandatory both sides): 1:1, FR-01
-- ---------------------------------------------------------------------
CREATE TABLE Accounts (
    accountID    INT AUTO_INCREMENT PRIMARY KEY,
    userID       INT NOT NULL UNIQUE,          -- UNIQUE enforces the 1:1
    userName     VARCHAR(50)  NOT NULL UNIQUE,
    passwordHash VARCHAR(255) NOT NULL,
    CONSTRAINT fk_accounts_user
        FOREIGN KEY (userID) REFERENCES Users(userID)
);
-- ---------------------------------------------------------------------
-- EquipmentInventory
-- FR-03, FR-14 (lifecycle: Available -> Reserved -> In Use -> Maintenance -> Available)
-- ---------------------------------------------------------------------
CREATE TABLE EquipmentInventory (
    equipmentID     INT AUTO_INCREMENT PRIMARY KEY,
    manufacturer    VARCHAR(100) NOT NULL,
    model           VARCHAR(100) NOT NULL,
    equipmentStatus ENUM('Available','Reserved','In Use','Maintenance') NOT NULL DEFAULT 'Available'
);
-- ---------------------------------------------------------------------
-- ConsumableInventory
-- FR-04, FR-16 (count must never go negative)
-- ---------------------------------------------------------------------
CREATE TABLE ConsumableInventory (
    consumableID  INT AUTO_INCREMENT PRIMARY KEY,
    manufacturer  VARCHAR(100) NOT NULL,
    model         VARCHAR(100) NOT NULL,
    count         INT NOT NULL DEFAULT 0,
    CONSTRAINT chk_consumable_count_nonnegative CHECK (count >= 0)
);
-- ---------------------------------------------------------------------
-- Reservations
-- FR-07/FR-08/FR-15 (no double-booking, enforced at application layer
-- via overlap check on equipmentID + time range)
-- consumableID is optional: not every reservation needs a consumable
-- ---------------------------------------------------------------------
CREATE TABLE Reservations (
    reservationID     INT AUTO_INCREMENT PRIMARY KEY,
    equipmentID       INT NOT NULL,
    consumableID      INT NULL,
    userID            INT NOT NULL,
    date              DATE NOT NULL,
    startTime         DATETIME NOT NULL,
    endTime           DATETIME NOT NULL,
    reservationStatus ENUM('Active','Completed','Cancelled') NOT NULL DEFAULT 'Active',
    CONSTRAINT fk_reservations_equipment
        FOREIGN KEY (equipmentID) REFERENCES EquipmentInventory(equipmentID),
    CONSTRAINT fk_reservations_consumable
        FOREIGN KEY (consumableID) REFERENCES ConsumableInventory(consumableID),
    CONSTRAINT fk_reservations_user
        FOREIGN KEY (userID) REFERENCES Users(userID)
);

-- ---------------------------------------------------------------------
-- ActiveMaintenanceTickets
-- FR-09 (student-submitted), FR-10 (system auto-generated), FR-18
-- EquipmentInventory -> ActiveMaintenanceTickets: 1:0..1 (one active ticket per equipment max)
-- Users -> ActiveMaintenanceTickets: 1:0..many (one technician can hold multiple active tickets)
-- Reservations -> ActiveMaintenanceTickets: 1:0..1 (at most one ticket per reservation, ever)
-- ---------------------------------------------------------------------
CREATE TABLE ActiveMaintenanceTickets (
    ticketID      INT AUTO_INCREMENT PRIMARY KEY,
    reservationID INT NOT NULL UNIQUE,          -- UNIQUE enforces "one ticket max per reservation"
    equipmentID   INT NOT NULL UNIQUE,          -- UNIQUE enforces "one active ticket max per equipment"
    userID        INT NOT NULL,                 -- technician; not UNIQUE, so one tech can hold many
    ticketStatus  ENUM('Open','In Progress','Closed') NOT NULL DEFAULT 'Open',
    startTime     DATETIME NOT NULL,
    endTime       DATETIME NULL,
    CONSTRAINT fk_activeticket_reservation
        FOREIGN KEY (reservationID) REFERENCES Reservations(reservationID),
    CONSTRAINT fk_activeticket_equipment
        FOREIGN KEY (equipmentID) REFERENCES EquipmentInventory(equipmentID),
    CONSTRAINT fk_activeticket_user
        FOREIGN KEY (userID) REFERENCES Users(userID)
);

-- ---------------------------------------------------------------------
-- MaintenanceTicketsLog
-- Archive of closed tickets. Independent of ActiveMaintenanceTickets by design
-- (per clarification: ticketID intentionally dropped, not carried over as an FK)
-- Reservations -> MaintenanceTicketsLog: 1:0..1 (same "one ticket ever" rule)
-- ---------------------------------------------------------------------
CREATE TABLE MaintenanceTicketsLog (
    maintenanceLogID INT AUTO_INCREMENT PRIMARY KEY,
    reservationID     INT NOT NULL UNIQUE,       -- UNIQUE enforces the 1:1 with Reservations
    equipmentID       INT NOT NULL,
    userID            INT NOT NULL,
    ticketStatus      ENUM('Closed','Cancelled') NOT NULL DEFAULT 'Closed',
    startTime         DATETIME NOT NULL,
    endTime           DATETIME NOT NULL,
    retired           BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_log_reservation
        FOREIGN KEY (reservationID) REFERENCES Reservations(reservationID),
    CONSTRAINT fk_log_equipment
        FOREIGN KEY (equipmentID) REFERENCES EquipmentInventory(equipmentID),
    CONSTRAINT fk_log_user
        FOREIGN KEY (userID) REFERENCES Users(userID)
);
-- ---------------------------------------------------------------------
-- AuditLogs
-- FR-17. System-generated, append-only — no UPDATE/DELETE permitted at the
-- application layer (see CRUD plan). timestamp defaults to insert time.
-- ---------------------------------------------------------------------
CREATE TABLE AuditLogs (
    auditLogID INT AUTO_INCREMENT PRIMARY KEY,
    userID     INT NOT NULL,
    action     VARCHAR(150) NOT NULL,
    timestamp  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_auditlog_user
        FOREIGN KEY (userID) REFERENCES Users(userID)
);
