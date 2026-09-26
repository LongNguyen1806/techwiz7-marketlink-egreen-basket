import { useState } from 'react';
import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/LazyImage.css';
/** Lazy-loaded image with blur-up placeholder for polish / perf. */
export function LazyImage({ src, alt, className }) {
    const [loaded, setLoaded] = useState(false);
    if (src === null || src === '') {
        return (<div className={cn('lazy-image--placeholder', className)} role="img" aria-label={alt}/>);
    }
    return (<img src={src} alt={alt} loading="lazy" decoding="async" onLoad={() => setLoaded(true)} className={cn('lazy-image', loaded ? 'lazy-image--loaded' : 'lazy-image--loading', className)}/>);
}

LazyImage.propTypes = {
    src: PropTypes.oneOfType([PropTypes.string, PropTypes.oneOf([null])]),
    alt: PropTypes.string.isRequired,
    className: PropTypes.string,
};

