import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../ui/ToastProvider";
import DocumentsPanel from "./DocumentsPanel";

const api = vi.hoisted(() => ({
  deleteDocument: vi.fn(),
  listDocuments: vi.fn(),
  presignDocumentDownload: vi.fn(),
  presignDocumentUpload: vi.fn(),
  uploadToS3PresignedUrl: vi.fn(),
  confirmDocumentUpload: vi.fn(),
}));

vi.mock("../../api", () => api);

function renderPanel() {
  return render(
    <ToastProvider>
      <DocumentsPanel jobId={1} />
    </ToastProvider>
  );
}

describe("DocumentsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listDocuments.mockResolvedValue([]);
  });

  it("shows toast when scan marks a document infected", async () => {
    const user = userEvent.setup();

    api.presignDocumentUpload.mockResolvedValueOnce({
      document: { id: 123, doc_type: "resume", original_filename: "resume.pdf", status: "pending", created_at: new Date().toISOString() },
      upload_url: "https://example.invalid/presigned/put",
    });
    api.uploadToS3PresignedUrl.mockResolvedValueOnce(undefined);
    api.confirmDocumentUpload.mockResolvedValueOnce({ message: "ok" });
    api.listDocuments
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([
        { id: 123, doc_type: "resume", original_filename: "resume.pdf", status: "infected", created_at: new Date().toISOString() },
      ]); // refresh after confirm

    renderPanel();

    const file = new File(["hello"], "resume.pdf", { type: "application/pdf" });
    const inputs = Array.from(document.querySelectorAll("input[type='file']"));
    await user.upload(inputs[0] as HTMLInputElement, file);

    expect(await screen.findByText("A document was blocked by malware scanning. Please upload a clean copy.")).toBeInTheDocument();
    expect(await screen.findByText("resume.pdf")).toBeInTheDocument();
  });

  it("uploads successfully (presign -> s3 -> confirm -> refresh) and shows toast", async () => {
    const user = userEvent.setup();

    api.presignDocumentUpload.mockResolvedValueOnce({
      document: { id: 123, doc_type: "resume", original_filename: "resume.pdf", status: "pending", created_at: new Date().toISOString() },
      upload_url: "https://example.invalid/presigned/put",
    });
    api.uploadToS3PresignedUrl.mockResolvedValueOnce(undefined);
    api.confirmDocumentUpload.mockResolvedValueOnce({ message: "ok" });
    api.listDocuments
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([
        { id: 123, doc_type: "resume", original_filename: "resume.pdf", status: "uploaded", created_at: new Date().toISOString() },
      ]); // refresh after confirm

    renderPanel();

    const file = new File(["hello"], "resume.pdf", { type: "application/pdf" });
    const inputs = Array.from(document.querySelectorAll("input[type='file']"));
    await user.upload(inputs[0] as HTMLInputElement, file);

    await waitFor(() => expect(api.presignDocumentUpload).toHaveBeenCalledWith(1, expect.anything()));
    await waitFor(() => expect(api.uploadToS3PresignedUrl).toHaveBeenCalledWith("https://example.invalid/presigned/put", file));
    await waitFor(() => expect(api.confirmDocumentUpload).toHaveBeenCalledWith(1, { document_id: 123, size_bytes: file.size }));

    expect(await screen.findByText("Upload complete.")).toBeInTheDocument();
    expect(await screen.findByText("resume.pdf")).toBeInTheDocument();
  });

  it("deletes successfully and shows toast", async () => {
    const user = userEvent.setup();
    api.listDocuments
      .mockResolvedValueOnce([
        { id: 55, doc_type: "resume", original_filename: "resume.pdf", status: "uploaded", created_at: new Date().toISOString() },
      ])
      .mockResolvedValueOnce([]); // after delete refresh
    api.deleteDocument.mockResolvedValueOnce({ message: "ok" });

    renderPanel();

    const delButtons = await screen.findAllByTitle("Delete");
    await user.click(delButtons[0]);

    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith(1, 55));
    expect(await screen.findByText("Document deleted.")).toBeInTheDocument();
  });

  it("shows toast on presign upload failure", async () => {
    const user = userEvent.setup();
    api.presignDocumentUpload.mockRejectedValueOnce(new Error("Presign failed"));

    renderPanel();

    const file = new File(["hello"], "resume.pdf", { type: "application/pdf" });
    const inputs = Array.from(document.querySelectorAll("input[type='file']"));
    expect(inputs.length).toBeGreaterThan(0);

    await user.upload(inputs[0] as HTMLInputElement, file);

    expect(await screen.findByText("Presign failed")).toBeInTheDocument();
  });

  it("shows toast on confirm upload failure", async () => {
    const user = userEvent.setup();
    api.presignDocumentUpload.mockResolvedValueOnce({
      document: { id: 123, doc_type: "resume", original_filename: "resume.pdf", status: "pending", created_at: new Date().toISOString() },
      upload_url: "https://example.invalid/presigned/put",
    });
    api.uploadToS3PresignedUrl.mockResolvedValueOnce(undefined);
    api.confirmDocumentUpload.mockRejectedValueOnce(new Error("Confirm failed"));

    renderPanel();

    const file = new File(["hello"], "resume.pdf", { type: "application/pdf" });
    const inputs = Array.from(document.querySelectorAll("input[type='file']"));
    await user.upload(inputs[0] as HTMLInputElement, file);

    expect(await screen.findByText("Confirm failed")).toBeInTheDocument();
  });

  it("shows toast when download fails", async () => {
    const user = userEvent.setup();

    api.listDocuments.mockResolvedValueOnce([
      {
        id: 55,
        doc_type: "resume",
        original_filename: "resume.pdf",
        content_type: "application/pdf",
        status: "uploaded",
        created_at: new Date().toISOString(),
      },
    ]);
    api.presignDocumentDownload.mockRejectedValueOnce(new Error("Document is not ready to download yet"));

    // Prevent window.open from erroring in test env.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).open = vi.fn();

    renderPanel();

    const downloadButtons = await screen.findAllByTitle("Download");
    await user.click(downloadButtons[0]);

    await waitFor(() => expect(api.presignDocumentDownload).toHaveBeenCalledWith(1, 55));
    expect((await screen.findAllByText("Document is not ready to download yet")).length).toBeGreaterThan(0);
  });
});


