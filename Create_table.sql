CREATE TABLE Airline
(
    airline_name VARCHAR(50) NOT NULL,
    PRIMARY KEY (airline_name)
);

CREATE TABLE Airport
(
    airport_name    VARCHAR(50) NOT NULL,
    city            VARCHAR(50) NOT NULL,
    PRIMARY KEY (airport_name)
);

CREATE TABLE Airplane
(
    airplane_id     INT NOT NULL,
    airline_name    VARCHAR(50) NOT NULL,
    seats           INT NOT NULL,
    PRIMARY KEY (airplane_id),
    FOREIGN KEY (airline_name)
        REFERENCES Airline(airline_name)
);

CREATE TABLE Flight
(
    airline_name    VARCHAR(50) NOT NULL,
    flight_number   VARCHAR(50) NOT NULL,
    price           DECIMAL(10,2) NOT NULL,
    flight_status   VARCHAR(20) NOT NULL,
    departure_time  DATETIME NOT NULL,
    arrival_time    DATETIME NOT NULL,
    departure_airport   VARCHAR(50) NOT NULL,
    arrival_airport     VARCHAR(50) NOT NULL,
    airplane_id         INT NOT NULL,
    PRIMARY KEY (airline_name, flight_number),
    FOREIGN KEY (airline_name, airplane_id)
        REFERENCES Airplane(airline_name, airplane_id),
    FOREIGN KEY (departure_airport)
        REFERENCES Airport(airport_name),
    FOREIGN KEY (arrival_airport)
        REFERENCES Airport(airport_name)
);

CREATE TABLE Customer
(
    email               VARCHAR(100) NOT NULL,
    customer_password   VARCHAR(100) NOT NULL,
    name_customer       VARCHAR(100) NOT NULL,
    phone_number        VARCHAR(20)  NOT NULL,
    passport_number     VARCHAR(20)  NOT NULL,
    passport_exp_date  DATE,
    passport_country   VARCHAR(50),
    date_of_birth      DATE,
    building_number    VARCHAR(20),
    street             VARCHAR(100),
    city               VARCHAR(50),
    state_name              VARCHAR(50),
    PRIMARY KEY (email)
);

CREATE TABLE Booking_agent
(
    Name_agent          VARCHAR(50) NOT NULL,
    email               VARCHAR(50) NOT NULL,
    agent_password      VARCHAR(50) NOT NULL,
    booking_agent_id    INT         NOT NULL,
    PRIMARY KEY (email),
    UNIQUE (booking_agent_id)
);

CREATE TABLE Agent_status
(
    agent_email     VARCHAR(50) NOT NULL,
    airline_name    VARCHAR(50) NOT NULL,
    PRIMARY KEY (agent_email, airline_name),
    FOREIGN KEY (agent_email)
        REFERENCES Booking_agent(email),
    FOREIGN KEY (airline_name)
        REFERENCES Airline(airline_name)
);

CREATE TABLE Airline_staff
(
    username        VARCHAR(50) NOT NULL,
    staff_email     VARCHAR(50) NOT NULL,
    password_stuff  VARCHAR(50) NOT NULL,
    airline_name    VARCHAR(50) NOT NULL,
    date_of_birth   DATE NOT NULL,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    PRIMARY KEY (username),
    FOREIGN KEY (airline_name)
        REFERENCES Airline(airline_name)
);

CREATE TABLE Permission_status
(
    username        VARCHAR(50) NOT NULL,
    staff_email     VARCHAR(50) NOT NULL,
    permission_type VARCHAR(20) NOT NULL,
    PRIMARY KEY (username, permission_type),
    FOREIGN KEY (username)
        REFERENCES Airline_staff(username)
);

CREATE TABLE Ticket
(
    ticket_id           VARCHAR(50) NOT NULL,
    airline_name        VARCHAR(50) NOT NULL,
    flight_number       VARCHAR(50) NOT NULL,
    customer_email      VARCHAR(100) NOT NULL,
    booking_agent_id    INT NULL,
    PRIMARY KEY (ticket_id),
    FOREIGN KEY (airline_name, flight_number)
        REFERENCES Flight(airline_name, flight_number),
    FOREIGN KEY (booking_agent_id)
        REFERENCES Booking_agent(booking_agent_id)
);

CREATE TABLE purchases
(
    ticket_id           VARCHAR(50) NOT NULL,
    customer_email      VARCHAR(100) NOT NULL,
    booking_agent_id    INT,
    purchase_time       DATETIME NOT NULL,
    PRIMARY KEY (ticket_id, customer_email),
    FOREIGN KEY (ticket_id) 
        REFERENCES Ticket(ticket_id),
    FOREIGN KEY (customer_email)
        REFERENCES Customer(email)
);

