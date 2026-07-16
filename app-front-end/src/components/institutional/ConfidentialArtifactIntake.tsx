import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { registerConfidentialArtifact } from '../../api/channelsOutcomes';

export default function ConfidentialArtifactIntake({ opportunityId }: { opportunityId: string }) {
  const queryClient = useQueryClient();
  const [type, setType] = useState<'pitch_deck' | 'email'>('pitch_deck');
  const [title, setTitle] = useState('');
  const [contentHash, setContentHash] = useState('');
  const [storageReference, setStorageReference] = useState('');
  const [retentionPolicy, setRetentionPolicy] = useState('standard');
  const mutation = useMutation({ mutationFn: () => registerConfidentialArtifact(opportunityId, { artifact_type: type, title: title.trim() || undefined, content_hash: contentHash.trim(), storage_reference: storageReference.trim(), retention_policy: retentionPolicy.trim() }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['institutional', 'evidence', opportunityId] }); setTitle(''); setContentHash(''); setStorageReference(''); } });
  return (
    <details className="mt-phi-6 border-t border-oxford/10 pt-phi-4">
      <summary className="type-action cursor-pointer">Register confidential evidence metadata</summary>
      <p className="type-body mt-phi-2 text-oxford/55">Aethria registers provenance and storage references here; it does not expose confidential file contents in the ledger.</p>
      <div className="mt-phi-3 grid gap-phi-3 sm:grid-cols-2">
        <select aria-label="Confidential artifact type" value={type} onChange={(event) => setType(event.target.value as typeof type)} className="border border-oxford/15 bg-paper px-3 py-2 type-action"><option value="pitch_deck">Pitch deck</option><option value="email">Email</option></select>
        <input aria-label="Artifact title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Artifact title" className="border border-oxford/15 bg-transparent px-3 py-2 text-sm" />
        <input aria-label="Content hash" value={contentHash} onChange={(event) => setContentHash(event.target.value)} placeholder="SHA-256 or content hash" className="border border-oxford/15 bg-transparent px-3 py-2 text-sm" />
        <input aria-label="Storage reference" value={storageReference} onChange={(event) => setStorageReference(event.target.value)} placeholder="Secure storage reference" className="border border-oxford/15 bg-transparent px-3 py-2 text-sm" />
        <input aria-label="Retention policy" value={retentionPolicy} onChange={(event) => setRetentionPolicy(event.target.value)} placeholder="Retention policy" className="border border-oxford/15 bg-transparent px-3 py-2 text-sm" />
      </div>
      <button type="button" onClick={() => mutation.mutate()} disabled={contentHash.trim().length < 8 || storageReference.trim().length < 3 || retentionPolicy.trim().length < 3 || mutation.isPending} className="type-action mt-phi-3 border border-oxford/15 px-3 py-2 disabled:opacity-35">Register artifact</button>
      {mutation.isSuccess ? <p role="status" className="type-body mt-phi-2 text-oxford/60">Confidential artifact metadata registered.</p> : null}
    </details>
  );
}

