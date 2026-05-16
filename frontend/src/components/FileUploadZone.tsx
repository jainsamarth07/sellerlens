import { useCallback, useState } from "react";
import { UploadCloud, FileSpreadsheet, X } from "lucide-react";

interface Props {
  multiple?: boolean;
  accept?: string;
  maxFiles?: number;
  onFiles: (files: File[]) => void;
  hint?: string;
  disabled?: boolean;
}

export default function FileUploadZone({
  multiple = false,
  accept = ".csv,.xlsx,.xls",
  maxFiles = 6,
  onFiles,
  hint,
  disabled = false,
}: Props) {
  const [drag, setDrag] = useState(false);
  const [files, setFiles] = useState<File[]>([]);

  const accept_files = useCallback(
    (incoming: FileList | null) => {
      if (disabled) return;
      if (!incoming) return;
      const list = Array.from(incoming).slice(0, maxFiles);
      setFiles(list);
      onFiles(list);
    },
    [disabled, maxFiles, onFiles],
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          if (disabled) return;
          e.preventDefault();
          setDrag(false);
          accept_files(e.dataTransfer.files);
        }}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition ${
          drag
            ? "border-brand-green bg-emerald-50"
            : "border-slate-300 bg-slate-50 hover:border-brand-green"
        }`}
      >
        <UploadCloud className="mx-auto text-slate-400" size={36} />
        <p className="mt-3 text-slate-700 font-medium">
          Drag & drop your settlement file{multiple ? "s" : ""} here
        </p>
        <p className="text-sm text-slate-500 mt-1">
          or{" "}
          <label className="text-brand-green font-semibold cursor-pointer hover:underline">
            browse
            <input
              type="file"
              accept={accept}
              multiple={multiple}
              disabled={disabled}
              onChange={(e) => accept_files(e.target.files)}
              className="hidden"
            />
          </label>
          {hint && <span className="text-slate-400"> · {hint}</span>}
        </p>
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-2">
          {files.map((f, i) => (
            <li
              key={i}
              className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <span className="flex items-center gap-2 text-slate-700">
                <FileSpreadsheet size={16} className="text-emerald-600" />
                {f.name}
                <span className="text-slate-400 text-xs">
                  ({(f.size / 1024).toFixed(1)} KB)
                </span>
              </span>
              <button
                onClick={() => {
                  const next = files.filter((_, j) => j !== i);
                  setFiles(next);
                  onFiles(next);
                }}
                className="text-slate-400 hover:text-brand-red"
              >
                <X size={16} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
