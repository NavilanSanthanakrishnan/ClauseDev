import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { getSession, isSignupAllowed, sendMagicLink } from '../lib/supabaseClient';
import { hydrateWorkflowFromServer, updateWorkflow } from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import { STEP_PATHS } from '../workflow/definitions';

function LoginPage() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [error, setError] = useState(null);
    const [info, setInfo] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const signupAllowed = useMemo(() => isSignupAllowed(), []);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError(null);
        setInfo(null);
        setIsSubmitting(true);

        try {
            const redirectTo = `${window.location.origin}/login`;
            await sendMagicLink(email.trim(), {
                shouldCreateUser: signupAllowed,
                redirectTo,
            });
            setInfo('Magic link sent. Open your email and click the one-time sign-in link.');
        } catch (err) {
            setError(err.message || 'Failed to send magic link');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleContinue = async () => {
        setError(null);
        const session = await getSession();
        if (!session?.access_token) {
            setError('No active session found yet. Use the magic link from your email first.');
            return;
        }
        await hydrateWorkflowFromServer();
        updateWorkflow({ currentStep: STEP_PATHS.EXTRACTION_INPUT });
        navigate(STEP_PATHS.EXTRACTION_INPUT);
    };

    return (
        <PageShell>
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '560px', margin: '0 auto' }}>
                    <div
                        style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '36px',
                        }}
                    >
                        <h1
                            style={{
                                fontFamily: "'Crimson Pro', serif",
                                fontSize: '40px',
                                fontWeight: 600,
                                color: '#1C1C1C',
                                marginBottom: '12px',
                            }}
                        >
                            Email Sign-In
                        </h1>
                        <p style={{ fontSize: '14px', color: '#6B5444', marginBottom: '24px' }}>
                            Enter your email to receive a one-time magic link.
                            {!signupAllowed && ' This environment only allows approved/invited users.'}
                        </p>

                        {error && (
                            <div
                                style={{
                                    backgroundColor: '#FEF2F2',
                                    border: '2px solid #EF4444',
                                    borderRadius: '4px',
                                    padding: '12px 16px',
                                    marginBottom: '16px',
                                    fontSize: '12px',
                                    color: '#6B5444',
                                }}
                            >
                                {error}
                            </div>
                        )}

                        {info && (
                            <div
                                style={{
                                    backgroundColor: '#ECFDF5',
                                    border: '2px solid #10B981',
                                    borderRadius: '4px',
                                    padding: '12px 16px',
                                    marginBottom: '16px',
                                    fontSize: '12px',
                                    color: '#065F46',
                                }}
                            >
                                {info}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            <div>
                                <label
                                    style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        display: 'block',
                                        marginBottom: '8px',
                                    }}
                                >
                                    Email
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '12px 14px',
                                        borderRadius: '4px',
                                        border: '1px solid #EAE3D5',
                                        fontSize: '14px',
                                    }}
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={isSubmitting || !email}
                                style={{
                                    width: '100%',
                                    padding: '14px 24px',
                                    fontSize: '10px',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.15em',
                                    borderRadius: '4px',
                                    border: 'none',
                                    backgroundColor: '#1C1C1C',
                                    color: '#FDFCF8',
                                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                                    opacity: isSubmitting ? 0.6 : 1,
                                }}
                            >
                                {isSubmitting ? 'Sending Link...' : 'Send Magic Link'}
                            </button>

                            <button
                                type="button"
                                onClick={handleContinue}
                                className="clause-btn clause-btn-secondary"
                                style={{ width: '100%' }}
                            >
                                I Opened The Link
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

export default LoginPage;
