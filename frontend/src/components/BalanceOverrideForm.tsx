import { useState } from 'react'
import { useSetBalanceOverride } from '../api/mutations'
import type { BankrollResponse } from '../../../shared/types'

type Props = {
  current: BankrollResponse['balance_override']
}

export function BalanceOverrideForm({ current }: Props) {
  const [amount, setAmount] = useState(current ? String(current.amount) : '')
  const [note, setNote] = useState(current?.note ?? '')
  const mut = useSetBalanceOverride()

  return (
    <form
      className="account-form"
      onSubmit={(e) => {
        e.preventDefault()
        const n = Number(amount)
        if (!Number.isFinite(n)) return
        mut.mutate({ amount: n, note })
      }}
    >
      <div className="account-form-row">
        <label className="account-form-label" htmlFor="balance-amount">
          Amount
        </label>
        <input
          id="balance-amount"
          className="account-form-input"
          type="text"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="700.00"
        />
      </div>
      <div className="account-form-row">
        <label className="account-form-label" htmlFor="balance-note">
          Note
        </label>
        <input
          id="balance-note"
          className="account-form-input"
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="DK app balance as of ..."
        />
      </div>
      {current && (
        <div className="account-form-help">
          Last updated {new Date(current.updated_at).toLocaleString()}
        </div>
      )}
      <div className="account-form-actions">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={mut.isPending || !amount.trim()}
        >
          {mut.isPending ? 'Saving...' : 'Save override'}
        </button>
        {mut.isSuccess && !mut.isPending && (
          <span className="account-form-status success">Saved.</span>
        )}
        {mut.isError && (
          <span className="account-form-status error">Save failed.</span>
        )}
      </div>
    </form>
  )
}
