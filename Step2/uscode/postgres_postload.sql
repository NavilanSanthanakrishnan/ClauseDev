ALTER TABLE public.usc_nodes
    ADD CONSTRAINT usc_nodes_pkey PRIMARY KEY (identifier);

ALTER TABLE public.usc_provisions
    ADD CONSTRAINT usc_provisions_pkey PRIMARY KEY (identifier);

ALTER TABLE public.usc_references
    ADD CONSTRAINT usc_references_pkey PRIMARY KEY (source_table, source_identifier, target_href, anchor_text);

ALTER TABLE public.usc_nodes
    ADD CONSTRAINT usc_nodes_parent_identifier_fkey
    FOREIGN KEY (parent_identifier) REFERENCES public.usc_nodes(identifier);

ALTER TABLE public.usc_provisions
    ADD CONSTRAINT usc_provisions_section_identifier_fkey
    FOREIGN KEY (section_identifier) REFERENCES public.usc_nodes(identifier);

CREATE INDEX usc_nodes_parent_sort_idx
    ON public.usc_nodes (parent_identifier, sort_order, label);

CREATE INDEX usc_nodes_citation_idx
    ON public.usc_nodes (citation);

CREATE INDEX usc_nodes_cornell_url_idx
    ON public.usc_nodes (cornell_url)
    WHERE cornell_url IS NOT NULL;

CREATE INDEX usc_provisions_section_idx
    ON public.usc_provisions (section_identifier, depth, sort_order, citation);

CREATE INDEX usc_provisions_parent_idx
    ON public.usc_provisions (parent_identifier, sort_order);

CREATE INDEX usc_provisions_citation_idx
    ON public.usc_provisions (citation);

CREATE INDEX usc_references_source_idx
    ON public.usc_references (source_table, source_identifier);

CREATE INDEX usc_references_target_idx
    ON public.usc_references (target_identifier);

CREATE OR REPLACE VIEW public.usc_sections AS
SELECT *
FROM public.usc_nodes
WHERE kind = 'section';
