import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileSignature,
  Loader2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  contractUrl,
  getVisaCaseDetail,
  getVisaCases,
  signContract,
  type VisaCaseDetail,
} from "@/lib/api/visa";
import { readableDate } from "@/lib/requests";

/**
 * Read your employment contract, accept it, and sign — without printing anything.
 *
 * The third panel, and the odd one of the three: the other two send documents to HCS-11
 * and this one accepts a document HCS-11 issued. It still takes the same two props and
 * looks its own case up, so the caller does not have to know which case a person has.
 *
 * Two things are deliberate.
 *
 * **The tick gates the button.** HCS-11's endpoint takes no body and no confirmation — a
 * bare POST signs the contract, and it cannot be undone, because a second attempt is
 * refused. So the only thing standing between a mis-tap and a signed employment contract
 * is this screen, and one deliberate gesture is the least it should ask for.
 *
 * **`is_signed` is read, never `signed_on`.** The date is set as soon as any job-offer
 * form is on the case, including an unsigned one the joiner uploaded, where HCS-11 falls
 * back to the day it arrived. The server has already asked HCS-11's own OFFER_SIGNED check
 * and written the answer down. Reading the date here would put "you have signed this" over
 * a form HCS-11 rejected.
 */
export function ContractSigning({
  employeeId,
  onClose,
}: {
  employeeId: string;
  onClose: () => void;
}) {
  const [state, setState] = useState<"loading" | "ready" | "no_case" | "error">("loading");
  const [caseData, setCaseData] = useState<VisaCaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [signing, setSigning] = useState(false);

  const load = useCallback(async (id: string) => {
    setState("loading");
    setError(null);
    try {
      const cases = await getVisaCases(id);
      const open = cases[0];
      if (!open) {
        setState("no_case");
        return;
      }
      setCaseData(await getVisaCaseDetail(open.case_id));
      setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the visa service");
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load(employeeId);
  }, [employeeId, load]);

  const sign = async () => {
    if (!caseData || signing) return;
    setSigning(true);
    try {
      // The whole case comes back, not just the contract: signing files the signed copy as
      // the job-offer document, so the checklist has moved too and replacing the lot is
      // the only way this panel and the one next door agree afterwards.
      setCaseData(await signContract(caseData.case.case_id));
      toast.success("Contract signed", {
        description: "It has been filed with your visa documents.",
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Signing failed";
      // Already signed is the answer, not a failure — somebody got there first, or a
      // second tap landed. Say so and show the signed state rather than an error.
      if (message.toLowerCase().includes("already been signed")) {
        toast.info("This contract is already signed");
        void load(employeeId);
      } else {
        setError(message);
        toast.error(message);
      }
    } finally {
      setSigning(false);
    }
  };

  if (state === "loading") {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading your contract…
        </CardContent>
      </Card>
    );
  }

  if (state === "no_case" || state === "error" || !caseData) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="py-10 text-center">
          <AlertTriangle className="size-5 mx-auto mb-3 text-amber-600" />
          <p className="text-sm">
            {state === "no_case"
              ? "There is no employment contract for you to sign."
              : /* Never "you have no contract": this is a service that could not be
                   reached, and the two are different answers. */
                (error ?? "Your contract could not be loaded.")}
          </p>
          <Button variant="outline" className="mt-4" onClick={onClose}>
            Close
          </Button>
        </CardContent>
      </Card>
    );
  }

  const contract = caseData.case.contract;
  // Keyed on the filed copy's id, which is null until there is one.
  //
  // Signing replaces what this address serves — the draft becomes the signed copy — but
  // the address itself does not change, so the frame kept showing the draft it had already
  // loaded while the banner underneath said the contract was signed. Somebody checking
  // their own signature would have found the page unsigned. Changing the query changes the
  // URL, which is what makes the frame go and fetch again.
  const pdf = `${contractUrl(caseData.case.case_id)}?v=${caseData.case.contract?.document_id ?? "draft"}`;
  const signed = contract?.is_signed ?? false;
  // A form on the case that HCS-11 has not accepted. Neither signed nor untouched.
  const returnedUnsigned = Boolean(contract?.signed_on) && !signed;
  const terms = [
    contract?.job_title,
    contract?.annual_salary_aed != null
      ? `AED ${contract.annual_salary_aed.toLocaleString("en-AE")}`
      : null,
    contract?.start_date ? `starting ${readableDate(contract.start_date)}` : null,
  ].filter(Boolean);

  return (
    <Card className="w-full max-w-4xl mx-auto max-h-[92vh] flex flex-col">
      <CardHeader className="shrink-0 border-b flex flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2">
            <FileSignature className="size-4.5 text-pink" />
            Your employment contract
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {signed
              ? `Signed on ${readableDate(contract?.signed_on)}`
              : contract?.prepared_on
                ? `Prepared for you on ${readableDate(contract.prepared_on)}`
                : "Issued with your visa application"}
          </p>
          {/*
            The headline terms, in one line rather than three cards.

            They used to be cards because the document could not be shown and a summary was
            all there was. The document is here now, and it prints these same three fields
            across its own head — so the cards had become a second copy sitting directly
            above the first. Kept at all, and kept small, because a browser that will not
            draw the PDF inline leaves this as the only thing on screen that says what is
            being agreed to.
          */}
          {terms.length > 0 && (
            <p className="mt-1 text-xs text-foreground">{terms.join(" · ")}</p>
          )}
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
          <X className="size-4" />
        </Button>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        {/*
          The contract itself, rather than a link to it.

          Asking somebody to tick "I have read this" beside a link that takes them away from
          the tick is asking them to accept it unread, and most people would. It is on the
          page they sign on, so reading it is the path of least resistance instead of a
          detour. The browser's own viewer draws it — nothing here renders a PDF, and the
          one thing worse than no viewer is a half-built one over an employment contract.

          `title` because a frame with no name is announced as "frame" and nothing else.
        */}
        <div className="flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-lg border bg-muted/20">
          <iframe
            // Chrome's own viewer, told to get out of the way: no toolbar (whose title
            // read "untitled", because the PDF carries no metadata and that is HCS-11's
            // file to name), no thumbnail rail (half the width, for a one-page document),
            // and fitted to the width so it reads as a page rather than a postage stamp.
            // Everything that strips — zoom, print, download — is one click away in the
            // tab below, which is the other reason that link stayed.
            src={`${pdf}#toolbar=0&navpanes=0&view=FitH`}
            title="Your employment contract"
            className="size-full flex-1 border-0"
          />
        </div>

        {/* Kept, and second. Inline PDFs do not render on every browser — most mobile ones
            hand the file to another app instead — so the frame above can come up blank with
            no error, and this is the way out when it does. */}
        <a
          href={pdf}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 self-start text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Open it in a new tab
          <ExternalLink className="size-3 shrink-0" />
        </a>

        {signed ? (
          <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
            <CheckCircle2 className="size-4 shrink-0 text-emerald-600 mt-0.5" />
            <p className="text-sm">
              You signed this contract. It has been filed with your visa documents as your
              signed job-offer form, so there is nothing further to send for it.
            </p>
          </div>
        ) : returnedUnsigned ? (
          <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
            <AlertTriangle className="size-4 shrink-0 text-amber-600 mt-0.5" />
            <p className="text-sm text-amber-800 dark:text-amber-300">
              There is a job-offer form on your case, but it has not been accepted — so your
              contract does not count as signed yet. Read it and sign below.
            </p>
          </div>
        ) : null}

        {!signed && (
          <label className="flex shrink-0 cursor-pointer items-start gap-2.5 rounded-lg border p-3 transition-colors hover:bg-muted/30">
            <Checkbox
              checked={accepted}
              onCheckedChange={(value) => setAccepted(value === true)}
              className="mt-0.5"
            />
            <span className="text-sm">
              I have read the contract and I accept employment on the terms set out in it.
            </span>
          </label>
        )}

        {error ? <p className="text-xs text-destructive">{error}</p> : null}
      </CardContent>

      <div className="shrink-0 border-t p-3 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
        {!signed && (
          <Button onClick={sign} disabled={!accepted || signing}>
            {signing ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Signing…
              </>
            ) : (
              "Sign my contract"
            )}
          </Button>
        )}
      </div>
    </Card>
  );
}
