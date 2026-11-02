"use client";

import { useParams } from "next/navigation";
import { MemoryStudio } from "@/components/memory-studio";

export default function AuditPage() {
  const params = useParams<{ id: string }>();
  return <MemoryStudio id={params.id} view="audit" />;
}
