import { useState, useEffect, useRef } from 'react';
import { apiService } from '../services/api';
import { API_CONFIG } from '../config/api';
import { createLogger } from '../utils/logger';

const logger = createLogger('useAPIHealth');

export function useAPIHealth() {
    const [isHealthy, setIsHealthy] = useState(false);
    const [version, setVersion] = useState(null);
    const [isChecking, setIsChecking] = useState(true);
    const intervalRef = useRef(null);
    const hasStartedRef = useRef(false);

    const checkHealth = async () => {
        try {
            const result = await apiService.checkHealth();
            setIsHealthy(result.isHealthy);
            setVersion(result.version);
            setIsChecking(false);
        } catch (error) {
            logger.warn('API health check hook failed', { error });
            setIsHealthy(false);
            setVersion(null);
            setIsChecking(false);
        }
    };

    useEffect(() => {
        if (!hasStartedRef.current) {
            hasStartedRef.current = true;
            checkHealth();

            intervalRef.current = setInterval(() => {
                checkHealth();
            }, API_CONFIG.HEALTH_CHECK_INTERVAL);
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    return { isHealthy, version, isChecking };
}
