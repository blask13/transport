--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8 (Debian 15.8-1.pgdg110+1)
-- Dumped by pg_dump version 15.8 (Debian 15.8-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: routes
--

CREATE SCHEMA tiger;


ALTER SCHEMA tiger OWNER TO routes;

--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: routes
--

CREATE SCHEMA tiger_data;


ALTER SCHEMA tiger_data OWNER TO routes;

--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: routes
--

CREATE SCHEMA topology;


ALTER SCHEMA topology OWNER TO routes;

--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: routes
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO routes;

--
-- Name: assignments; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.assignments (
    id bigint NOT NULL,
    parcel_id bigint NOT NULL,
    route_id bigint NOT NULL,
    status text DEFAULT 'offered'::text NOT NULL,
    delta_distance_m double precision,
    delta_duration_s double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT assignments_status_check CHECK ((status = ANY (ARRAY['offered'::text, 'accepted'::text, 'rejected'::text, 'expired'::text])))
);


ALTER TABLE public.assignments OWNER TO routes;

--
-- Name: assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.assignments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.assignments_id_seq OWNER TO routes;

--
-- Name: assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.assignments_id_seq OWNED BY public.assignments.id;


--
-- Name: disputes; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.disputes (
    id bigint NOT NULL,
    parcel_id bigint NOT NULL,
    reported_by bigint,
    courier_id bigint,
    reason text NOT NULL,
    courier_response text,
    resolution text,
    status text DEFAULT 'open'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT chk_disputes_status CHECK ((status = ANY (ARRAY['open'::text, 'resolved'::text, 'escalated'::text])))
);


ALTER TABLE public.disputes OWNER TO routes;

--
-- Name: disputes_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.disputes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.disputes_id_seq OWNER TO routes;

--
-- Name: disputes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.disputes_id_seq OWNED BY public.disputes.id;


--
-- Name: parcels; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.parcels (
    id bigint NOT NULL,
    sender_id bigint,
    pickup_point public.geometry(Point,4326) NOT NULL,
    drop_point public.geometry(Point,4326) NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    title text,
    pickup_after timestamp with time zone,
    pickup_before timestamp with time zone,
    dropoff_after timestamp with time zone,
    dropoff_before timestamp with time zone,
    weight_kg double precision,
    size_class text,
    CONSTRAINT chk_parcels_status CHECK ((status = ANY (ARRAY['pending'::text, 'offered'::text, 'accepted'::text, 'delivered'::text, 'disputed'::text, 'completed'::text, 'rejected'::text, 'cancelled'::text])))
);


ALTER TABLE public.parcels OWNER TO routes;

--
-- Name: parcels_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.parcels_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.parcels_id_seq OWNER TO routes;

--
-- Name: parcels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.parcels_id_seq OWNED BY public.parcels.id;


--
-- Name: route_history; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.route_history (
    id bigint NOT NULL,
    route_id bigint NOT NULL,
    changed_by text NOT NULL,
    change_type text NOT NULL,
    parcel_id bigint,
    old_geom public.geometry(LineString,4326),
    old_distance_m double precision,
    old_duration_s double precision,
    new_geom public.geometry(LineString,4326),
    new_distance_m double precision,
    new_duration_s double precision,
    delta_distance_m double precision,
    delta_duration_s double precision,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_route_history_change_type CHECK ((change_type = ANY (ARRAY['created'::text, 'parcel_accepted'::text, 'cancelled'::text])))
);


ALTER TABLE public.route_history OWNER TO routes;

--
-- Name: route_history_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.route_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.route_history_id_seq OWNER TO routes;

--
-- Name: route_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.route_history_id_seq OWNED BY public.route_history.id;


--
-- Name: route_parcel_matches; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.route_parcel_matches (
    id bigint NOT NULL,
    route_id bigint NOT NULL,
    parcel_id bigint NOT NULL,
    status text DEFAULT 'proposed'::text NOT NULL,
    delta_distance_m double precision NOT NULL,
    delta_duration_s double precision NOT NULL,
    base_distance_m double precision,
    base_duration_s double precision,
    new_distance_m double precision,
    new_duration_s double precision,
    pickup_to_route_m double precision,
    drop_to_route_m double precision,
    algorithm_version text DEFAULT 'mvp-0.1'::text NOT NULL,
    debug text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_route_parcel_match_status CHECK ((status = ANY (ARRAY['proposed'::text, 'accepted'::text, 'rejected'::text, 'expired'::text])))
);


ALTER TABLE public.route_parcel_matches OWNER TO routes;

--
-- Name: route_parcel_matches_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

ALTER TABLE public.route_parcel_matches ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.route_parcel_matches_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: routes; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.routes (
    id bigint NOT NULL,
    courier_id bigint NOT NULL,
    title text,
    start_point public.geometry(Point,4326) NOT NULL,
    end_point public.geometry(Point,4326) NOT NULL,
    geom public.geometry(LineString,4326) NOT NULL,
    distance_m double precision NOT NULL,
    duration_s double precision NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.routes OWNER TO routes;

--
-- Name: routes_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.routes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.routes_id_seq OWNER TO routes;

--
-- Name: routes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.routes_id_seq OWNED BY public.routes.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: routes
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    handle text NOT NULL,
    role text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT users_role_check CHECK ((role = ANY (ARRAY['courier'::text, 'sender'::text, 'admin'::text])))
);


ALTER TABLE public.users OWNER TO routes;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: routes
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO routes;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: routes
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: assignments id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.assignments ALTER COLUMN id SET DEFAULT nextval('public.assignments_id_seq'::regclass);


--
-- Name: disputes id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.disputes ALTER COLUMN id SET DEFAULT nextval('public.disputes_id_seq'::regclass);


--
-- Name: parcels id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.parcels ALTER COLUMN id SET DEFAULT nextval('public.parcels_id_seq'::regclass);


--
-- Name: route_history id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_history ALTER COLUMN id SET DEFAULT nextval('public.route_history_id_seq'::regclass);


--
-- Name: routes id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.routes ALTER COLUMN id SET DEFAULT nextval('public.routes_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: assignments assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_pkey PRIMARY KEY (id);


--
-- Name: disputes disputes_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_pkey PRIMARY KEY (id);


--
-- Name: parcels parcels_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.parcels
    ADD CONSTRAINT parcels_pkey PRIMARY KEY (id);


--
-- Name: route_history route_history_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_history
    ADD CONSTRAINT route_history_pkey PRIMARY KEY (id);


--
-- Name: route_parcel_matches route_parcel_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_parcel_matches
    ADD CONSTRAINT route_parcel_matches_pkey PRIMARY KEY (id);


--
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (id);


--
-- Name: users users_handle_key; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_handle_key UNIQUE (handle);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_assignments_parcel; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_assignments_parcel ON public.assignments USING btree (parcel_id);


--
-- Name: idx_assignments_route; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_assignments_route ON public.assignments USING btree (route_id);


--
-- Name: idx_disputes_parcel; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_disputes_parcel ON public.disputes USING btree (parcel_id);


--
-- Name: idx_disputes_status; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_disputes_status ON public.disputes USING btree (status) WHERE (status = 'open'::text);


--
-- Name: idx_parcels_drop_gist; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_parcels_drop_gist ON public.parcels USING gist (drop_point);


--
-- Name: idx_parcels_pickup_gist; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_parcels_pickup_gist ON public.parcels USING gist (pickup_point);


--
-- Name: idx_parcels_status; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_parcels_status ON public.parcels USING btree (status);


--
-- Name: idx_route_history_created_at; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_route_history_created_at ON public.route_history USING btree (created_at DESC);


--
-- Name: idx_route_history_new_geom; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_route_history_new_geom ON public.route_history USING gist (new_geom);


--
-- Name: idx_route_history_old_geom; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_route_history_old_geom ON public.route_history USING gist (old_geom);


--
-- Name: idx_route_history_route_id; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_route_history_route_id ON public.route_history USING btree (route_id);


--
-- Name: idx_routes_active; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_routes_active ON public.routes USING btree (is_active);


--
-- Name: idx_routes_courier; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_routes_courier ON public.routes USING btree (courier_id);


--
-- Name: idx_routes_geom_gist; Type: INDEX; Schema: public; Owner: routes
--

CREATE INDEX idx_routes_geom_gist ON public.routes USING gist (geom);


--
-- Name: assignments assignments_parcel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_parcel_id_fkey FOREIGN KEY (parcel_id) REFERENCES public.parcels(id) ON DELETE CASCADE;


--
-- Name: assignments assignments_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.assignments
    ADD CONSTRAINT assignments_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- Name: disputes disputes_courier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_courier_id_fkey FOREIGN KEY (courier_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: disputes disputes_parcel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_parcel_id_fkey FOREIGN KEY (parcel_id) REFERENCES public.parcels(id) ON DELETE CASCADE;


--
-- Name: disputes disputes_reported_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_reported_by_fkey FOREIGN KEY (reported_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: parcels parcels_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.parcels
    ADD CONSTRAINT parcels_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: route_history route_history_parcel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_history
    ADD CONSTRAINT route_history_parcel_id_fkey FOREIGN KEY (parcel_id) REFERENCES public.parcels(id) ON DELETE SET NULL;


--
-- Name: route_history route_history_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_history
    ADD CONSTRAINT route_history_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- Name: route_parcel_matches route_parcel_matches_parcel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_parcel_matches
    ADD CONSTRAINT route_parcel_matches_parcel_id_fkey FOREIGN KEY (parcel_id) REFERENCES public.parcels(id) ON DELETE CASCADE;


--
-- Name: route_parcel_matches route_parcel_matches_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.route_parcel_matches
    ADD CONSTRAINT route_parcel_matches_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- Name: routes routes_courier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: routes
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_courier_id_fkey FOREIGN KEY (courier_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

