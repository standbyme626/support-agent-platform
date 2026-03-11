"use client";

import { useEffect, useState } from "react";
import {
  createKbDoc,
  deleteKbDoc,
  fetchKbList,
  updateKbDoc,
  type KbCreatePayload,
  type KbItem,
  type KbSourceType,
  type KbUpdatePayload
} from "@/lib/api/kb";

type State = {
  loading: boolean;
  error: string | null;
  items: KbItem[];
  total: number;
  page: number;
  pageSize: number;
  q: string;
  actionLoading: boolean;
  actionError: string | null;
  actionSuccess: string | null;
};

type CreateInput = Omit<KbCreatePayload, "source_type">;

function buildQuery(page: number, pageSize: number, sourceType: KbSourceType, q: string) {
  return {
    page,
    page_size: pageSize,
    source_type: sourceType,
    q: q.trim().length > 0 ? q.trim() : undefined
  };
}

export function useKB(sourceType: KbSourceType) {
  const [state, setState] = useState<State>({
    loading: true,
    error: null,
    items: [],
    total: 0,
    page: 1,
    pageSize: 20,
    q: "",
    actionLoading: false,
    actionError: null,
    actionSuccess: null
  });

  async function load(page: number, q: string) {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchKbList(buildQuery(page, state.pageSize, sourceType, q));
      setState((previous) => ({
        ...previous,
        loading: false,
        error: null,
        items: response.items,
        total: response.total
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load KB documents"
      }));
    }
  }

  useEffect(() => {
    void load(state.page, state.q);
  }, [sourceType, state.page, state.pageSize, state.q]);

  async function createDoc(input: CreateInput) {
    setState((previous) => ({
      ...previous,
      actionLoading: true,
      actionError: null,
      actionSuccess: null
    }));
    try {
      const response = await createKbDoc({
        ...input,
        source_type: sourceType
      });
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: null,
        actionSuccess: `Created ${response.data.doc_id}`,
        items: [response.data, ...previous.items],
        total: previous.total + 1
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: error instanceof Error ? error.message : "Failed to create KB document"
      }));
    }
  }

  async function patchDoc(docId: string, patch: KbUpdatePayload) {
    setState((previous) => ({
      ...previous,
      actionLoading: true,
      actionError: null,
      actionSuccess: null
    }));
    try {
      const response = await updateKbDoc(docId, patch);
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: null,
        actionSuccess: `Updated ${response.data.doc_id}`,
        items: previous.items.map((item) => (item.doc_id === docId ? response.data : item))
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: error instanceof Error ? error.message : "Failed to update KB document"
      }));
    }
  }

  async function removeDoc(docId: string) {
    setState((previous) => ({
      ...previous,
      actionLoading: true,
      actionError: null,
      actionSuccess: null
    }));
    try {
      await deleteKbDoc(docId);
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: null,
        actionSuccess: `Deleted ${docId}`,
        items: previous.items.filter((item) => item.doc_id !== docId),
        total: Math.max(0, previous.total - 1)
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        actionLoading: false,
        actionError: error instanceof Error ? error.message : "Failed to delete KB document"
      }));
    }
  }

  return {
    ...state,
    setPage: (page: number) => setState((previous) => ({ ...previous, page })),
    setQuery: (q: string) => setState((previous) => ({ ...previous, page: 1, q })),
    clearQuery: () => setState((previous) => ({ ...previous, page: 1, q: "" })),
    clearActionState: () =>
      setState((previous) => ({ ...previous, actionError: null, actionSuccess: null })),
    refetch: () => load(state.page, state.q),
    createDoc,
    updateDoc: patchDoc,
    deleteDoc: removeDoc
  };
}
