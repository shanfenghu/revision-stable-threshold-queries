"""Complete scalar audits, matched controls and retrospective diagnostics.

Each fit uses its own calibration rank; scales and the selected optimum set use
training alone. Numeric exactness concerns recorded count/log coordinates.
"""
from fractions import Fraction as F
from datetime import date
from pathlib import Path
import csv
import json
import math
import statistics
import time
from . import sources, workloads as w, study, affine as p, rank_constraints as r
from . import reproduce as replay, set_band, training_loss, adverse

def project(values,domain):
    """Exact contrasts of recorded count/log coordinates; no rounded intermediate sums."""
    if domain=='gdp':return [values[a]-values[a+lag] for a in range(4) for lag in (1,4)]
    return [sum(values[a:a+k],F(0))/k-sum(values[a+k:a+2*k],F(0))/k for a in range(4) for k in (1,2,4)]


def rows(units,domain):
    result=[]
    for u in units:
        x=list(map(F,u['raw_inputs']));y=list(map(F,u['raw_targets']))
        basis=[(v if domain=='ili' else F(1))/(j+1) for j,v in enumerate(x)]
        base,slope,target=project(x,domain),project(basis,domain),project(y,domain)
        # Count means have power-of-two denominators; close GDP logs satisfy
        # exact subtraction in the stored binary coordinate representation.
        assert all(a==F(b) for a,b in zip(base,u['inputs']))
        assert all(a==F(b) for a,b in zip(target,u['targets']))
        result.append([(a,b,y,F(z)) for a,b,y,z in zip(base,slope,target,u['inputs'])])
    return result


def build(calibration,evaluation,scales):
    lines=p.family_lines(calibration,scales)
    k=math.ceil((len(calibration)+1)*.95)
    path=p.rank_path(lines,k)
    rank_checks=p.verify_rank_path(path,lines,k)
    atoms=p.decision_atoms(path,evaluation,scales)
    atom_checks=p.verify_atoms(path,atoms,evaluation,scales)
    return path,atoms,{'rank':k,'q_pieces':len(path),'decision_atoms':len(atoms),'rank_verification_checks':rank_checks,'atom_verification_checks':atom_checks}


def original_point(units,calibration,beta,scales,domain,oriented=False):
    scores=[]
    for u in calibration:
        mu=w.predict(u,beta,domain)
        values=[(1 if x>=0 else -1)*(m-y)/s if oriented else abs(m-y)/s
                for x,m,y,s in zip(u['inputs'],mu,u['targets'],scales)]
        scores.append(max(values))
    q,k=sources.cp_quantile(scores,.05)
    reused=wrong=mask=0;index=0
    for u in units:
        for x,y,mu,s in zip(u['inputs'],u['targets'],w.predict(u,beta,domain),scales):
            accept=w.reuse(x,mu,q*s)
            if accept:
                reused+=1;mask|=1<<index
                wrong+=((x>=0)!=(y>=0))
            index+=1
    return {'reused':reused,'wrong_reuses':wrong,'utility_total':reused-20*wrong,'q':q,'rank':k,'reuse_mask':hex(mask)}


def fidelity(units,calibration,scales,domain,atoms):
    mismatches=[];max_error=0.0
    affine=rows(units,domain)
    for beta in study.GRID:
        atom=next(a for a in atoms if a.region.contains(F(beta)))
        actual=original_point(units,calibration,beta,scales,domain)
        if atom.reused!=int(actual['reuse_mask'],16) or atom.utility!=actual['utility_total']:
            mismatches.append({'beta':beta,'affine_reused':p.count_bits(atom.reused),'float_reused':actual['reused'],'affine_utility':atom.utility,'float_utility':actual['utility_total'],
                               'different_answer_mask':hex(atom.reused^int(actual['reuse_mask'],16))})
        for u,family in zip(units,affine):
            for mu,(base,slope,_,_) in zip(w.predict(u,beta,domain),family):
                max_error=max(max_error,abs(mu-float(base+F(beta)*slope)))
    return {'grid_points_checked':201,'decision_mismatches':mismatches,'max_prediction_absolute_difference':max_error}


def baseline_records(cal,test,fit,domain):
    out={}
    for model,beta in fit['models'].items():
        standard=original_point(test,cal,beta,fit['scales'],domain)
        oriented=original_point(test,cal,beta,fit['scales'],domain,True)
        assert oriented['q']<=standard['q']
        assert int(standard['reuse_mask'],16)&~int(oriented['reuse_mask'],16)==0
        out[model]={'beta':beta,'symmetric':standard,'oriented_one_sided_control':oriented}
    return out


def diagnostic_controls(train, calibration, test, fit, domain, path, selected):
    """Remove baseline quantization and describe center/radius geometry, not causality."""
    numerator=denominator=0.0
    for group in study.training_parts(train):
        for u in group:
            x,y,b=study.coordinates(u,domain)
            numerator+=math.fsum(bb*(yy-xx) for xx,yy,bb in zip(x,y,b))
            denominator+=math.fsum(bb*bb for bb in b)
    beta=max(-.5,min(.5,numerator/denominator))
    ls=original_point(test,calibration,beta,fit['scales'],domain)
    region=selected[0]
    representative=(region.left+region.right)/2
    reference=F(fit['models']['revision_loss'])
    examples=rows(test,domain)
    def count(center_beta,radius_beta):
        q=p.at(path,radius_beta)(radius_beta);out=0
        for family in examples:
            for (base,slope,target,current),scale in zip(family,fit['scales']):
                mu=base+slope*center_beta;r=q*F(scale)
                out+=mu-r>=0 if current>=0 else mu+r<0
        return out
    matrix=[[count(c,r) for r in (reference,representative)] for c in (reference,representative)]
    scores=[]
    q=p.at(path,representative)(representative)
    for i,(unit,family) in enumerate(zip(calibration,rows(calibration,domain))):
        values=[abs(target-base-slope*representative)/F(scale) for (base,slope,target,_),scale in zip(family,fit['scales'])]
        if max(values)==q:
            scores.append({'calibration_issue':study.unit_label(unit['issue'],domain),
                           'query_indices':[j for j,v in enumerate(values) if v==q]})
    return {'continuous_revision_loss_beta':beta,'continuous_revision_loss_later_outcome':ls,
            'training_only_representative_beta':str(representative),'representative_beta_approx':float(representative),
            'crossed_center_radius_reused':matrix,
            'crossed_matrix_order':'rows=center, columns=radius: original revision fit then training-only optimal-set representative; algebraic diagnostic, not valid alternative calibration policies',
            'representative_final_quantile':float(q),'quantile_witnesses':scores}



def load_units(inputs, fits=None):
    """Verify exact inputs and reconstruct the two distinct source populations."""
    records = replay.verify_inputs(inputs)
    role = lambda name: [v for v in records if v['role'] == name]
    csv_path = inputs / role('ili_table')[0]['path']
    early, _ = w.ili_ledger(w.read_source(inputs, role('ili_training')), csv_path)
    later, ledger = study.new_ili_units(inputs, role('ili_evaluation'), csv_path)
    output = w.gdp_units(inputs / role('gdp_table')[0]['path'])
    if fits is None:
        fits = {domain: study.choose_fit(units, domain)
                for domain, units in [('ili', early), ('gdp', output)]}
    replay.compare(replay.fit_summary(fits), replay.read_json(replay.ROOT / 'expected/fits.json'))
    return {'ili': (early, later), 'gdp': (output, output)}, fits, ledger


def select_windows(units, fit, domain, protocol, ledger):
    """Select by issue/target/reference identities, never by fitted outcomes."""
    calibration, original = study.split_final(units, fit, domain, protocol)
    if domain == 'ili':
        endpoint = study.phase_windows(domain, protocol)[1][1]
        subsequent = [u for u in units if u['issue'] > endpoint]
        if len(subsequent) != 2:
            raise ValueError('The retained subsequent report cohort must contain two families')
        if max(u['target'] for u in subsequent) > date.fromisoformat(ledger['latest_acquired_release']).toordinal():
            raise ValueError('Subsequent target exceeds retained source availability')
    else:
        subsequent = sorted((u for u in units if u['issue'] > max(v['issue'] for v in original)),
                            key=lambda u: u['issue'])[:12]
    windows = {'original': original, 'subsequent': subsequent}
    if domain == 'gdp':
        prior = original + subsequent
        last_target = max(u['target'] for u in prior)
        last_reference = max(v for u in prior for v in u['support'])
        disjoint = [u for u in sorted(units, key=lambda u: u['issue'])
                    if u['issue'] > last_target and min(u['support']) > last_reference][:12]
        if len(subsequent) != 12 or len(disjoint) != 12:
            raise ValueError('The retained output windows require twelve eligible vintages each')
        windows['disjoint'] = disjoint
    return calibration, windows


def quartile_scales(units):
    """Use nearest-rank lower quartile of the same positive scale-phase revisions."""
    values = [[abs(y-x) for x, y in zip(u['inputs'], u['targets'])] for u in units]
    positive = sorted(v for family in values for v in family if v > 0)
    if not positive:
        raise ValueError('Unsupported scale: no positive training revisions')
    floor = positive[math.ceil(len(positive)/4)-1]
    medians = [statistics.median(v[j] for v in values) for j in range(len(values[0]))]
    return [max(v, floor) for v in medians], floor


def rank_atoms(atoms):
    """Represent envelope atoms for a comparison with the rank formulation."""
    return [(r.Interval(a.region.left, a.region.right, a.region.left_closed,
                        a.region.right_closed), a.reused, a.wrong) for a in atoms]


def region_key(regions):
    return [(v.left, v.right, v.lc, v.rc) for v in regions]


def reweight(atoms, cost):
    """Reuse geometry is fixed; only the declared R-(cost+1)W reward changes."""
    return [p.Atom(a.region, a.reused, a.wrong,
                   p.count_bits(a.reused)-(cost+1)*p.count_bits(a.wrong)) for a in atoms]


def recorded_scales(values):
    """Preserve binary input scales exactly at both formulation boundaries."""
    result = [F(value) for value in values]
    if not result or any(value <= 0 for value in result):
        raise ValueError('Positive finite fixed scales required')
    return result


def run(inputs, output, fits=None):
    """Reconstruct all audit diagnostics into a new directory and check references.

    The saved reference summaries are read only. Full decision partitions are
    recomputed by two formulations and compared after removing irrelevant cuts.
    This checks computational consistency, not exchangeability or future risk.
    """
    inputs, output = Path(inputs), Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new reproduction directory')
    started = time.monotonic()
    pools, fits, ledger = load_units(inputs, fits)
    protocol = replay.read_json(replay.ROOT / 'protocol.json')
    adverse_results = {d: adverse.run_domain(early, d) for d, (early, _) in pools.items()}
    replay.compare(replay.adverse_summary(adverse_results), replay.read_json(replay.ROOT / 'expected/adverse-summary.json'))
    results, certificates, verification = {}, {}, {}
    for domain, (early, units) in pools.items():
        parts = study.training_parts(early)
        calibration, windows = select_windows(units, fits[domain], domain, protocol, ledger)
        inner_cal, inner_eval, cal_rows = rows(parts[1], domain), rows(parts[2], domain), rows(calibration, domain)
        alt_scales, alt_floor = quartile_scales(parts[0])
        results[domain], certificates[domain], verification[domain] = {}, {}, {}
        for policy, scales, floor in [('primary', fits[domain]['scales'], fits[domain]['pooled_positive_median_floor']),
                                      ('lower_quartile_floor', alt_scales, alt_floor)]:
            numeric_scales = scales
            scales = recorded_scales(scales)
            print('Auditing', domain, policy, flush=True)
            inner_path, inner, inner_checks = build(inner_cal, inner_eval, scales)
            best = max(a.utility for a in inner)
            regions = p.merge_regions([a for a in inner if a.utility == best])
            direct_inner = r.phase(r.score_lines(inner_cal, scales), inner_eval, scales, inner_checks['rank'])
            ref_best, ref_regions = r.optimum(direct_inner)
            if r.record_atoms(rank_atoms(inner)) != r.record_atoms(direct_inner):
                raise ValueError('Inner decision formulations disagree')
            expected_regions = [(v.left, v.right, v.left_closed, v.right_closed) for v in regions]
            if best != ref_best or expected_regions != region_key(ref_regions):
                raise ValueError('Training optimum formulations disagree')
            fidelity_inner = fidelity(parts[2], parts[1], scales, domain, inner)
            if fidelity_inner['decision_mismatches']:
                raise ValueError('Inner floating decisions differ from recorded affine model')
            cost_sets = {}
            for cost in ([9, 19, 39] if policy == 'primary' else [19]):
                weighted = reweight(inner, cost)
                maximum = max(a.utility for a in weighted)
                cost_sets[str(cost)] = [p.region_record(v) for v in p.merge_regions([a for a in weighted if a.utility == maximum])]
            record = {'floor': floor, 'scales': numeric_scales, 'inner_maximum': best,
                      'training_optimal_regions': [p.region_record(v) for v in regions],
                      'inner_wrong_range': [min(p.count_bits(a.wrong) for a in inner), max(p.count_bits(a.wrong) for a in inner)],
                      'cost_optimum_sets': cost_sets, 'windows': {}}
            certificate = {'inner_path': p.path_record(inner_path), 'inner_atoms': p.atoms_record(inner), 'windows': {}}
            verify = {'inner': inner_checks, 'inner_floating': fidelity_inner,
                      'direct_inner_checks': r.check_atoms(direct_inner, inner_cal, inner_eval, scales, inner_checks['rank']), 'windows': {}}
            final_lines = p.family_lines(cal_rows, scales)
            final_rank = math.ceil((len(calibration)+1)*.95)
            final_path = p.rank_path(final_lines, final_rank)
            p.verify_rank_path(final_path, final_lines, final_rank)
            q_set, set_rank, _ = set_band.quantile(cal_rows, regions, scales)
            for name, test in windows.items():
                test_rows = rows(test, domain)
                atoms = p.decision_atoms(final_path, test_rows, scales)
                p.verify_atoms(final_path, atoms, test_rows, scales)
                direct = r.phase(r.score_lines(cal_rows, scales), test_rows, scales, final_rank)
                if r.record_atoms(rank_atoms(atoms)) != r.record_atoms(direct):
                    raise ValueError('Final complete decision formulations disagree')
                selected = p.restrict(atoms, regions)
                answers = len(test)*len(scales)
                summary = p.outcome_range(selected, answers)
                controls = diagnostic_controls(early, calibration, test, {**fits[domain], 'scales': scales}, domain, final_path, regions)
                references = {model: original_point(test, calibration, beta, scales, domain)
                              for model, beta in {**fits[domain]['models'], 'continuous_revision': controls['continuous_revision_loss_beta']}.items()}
                band = set_band.evaluate(test_rows, regions, scales, q_set)
                floating_mask, floating_q = set_band.direct_float(cal_rows, test_rows, regions, scales)
                if floating_mask != int(band['reuse_mask'], 16):
                    raise ValueError('Enclosing-band floating decisions disagree')
                always = int(summary['always_mask'], 16)
                if always & ~int(band['reuse_mask'], 16):
                    raise ValueError('Observed enclosing band loses an always-retained answer')
                window = {'answers': answers, 'issues': [study.unit_label(u['issue'], domain) for u in test],
                          'outcomes': summary, 'references': references,
                          'set_band': {k: v for k, v in band.items() if k != 'expanded_bounds'}}
                if policy == 'primary':
                    loss = training_loss.solve(p.atoms_record(inner), p.atoms_record(atoms), references['continuous_revision']['utility_total'])
                    loss['normalized_minimum_loss'] = str(F(loss['minimum_training_loss'], len(parts[2])*len(scales)))
                    witness = loss['witness']
                    beta = F(witness['beta'])
                    ir, iw, _ = r.direct(inner_cal, inner_eval, scales, inner_checks['rank'], beta)
                    lr, lw, _ = r.direct(cal_rows, test_rows, scales, final_rank, beta)
                    if (p.count_bits(ir)-20*p.count_bits(iw), p.count_bits(lr)-20*p.count_bits(lw)) != (witness['training_utility'], witness['later_utility']):
                        raise ValueError('Training-loss witness failed direct replay')
                    window['training_loss'] = {k: loss[k] for k in ['minimum_training_loss', 'normalized_minimum_loss', 'target_later_utility']}
                    certificate.setdefault('training_loss_witnesses', {})[name] = witness
                    window['one_sided'] = baseline_records(calibration, test, {**fits[domain], 'scales': scales}, domain)
                record['windows'][name] = window
                certificate['windows'][name] = {'atoms': p.atoms_record(atoms), 'set_expanded_bounds': band['expanded_bounds']}
                verify['windows'][name] = {'direct_rank_checks': r.check_atoms(direct, cal_rows, test_rows, scales, final_rank),
                                          'set_band_rank': set_rank, 'set_floating_q_difference': abs(float(q_set)-floating_q),
                                          'floating': fidelity(test, calibration, scales, domain, atoms)}
                if verify['windows'][name]['floating']['decision_mismatches']:
                    raise ValueError('Final floating decisions differ from recorded affine model')
            results[domain][policy], certificates[domain][policy], verification[domain][policy] = record, certificate, verify
    replay.compare(replay.audit_summary(results), replay.read_json(replay.ROOT / 'expected/audits.json'))
    output.mkdir(parents=True)
    for name, value in [('summary', results), ('certificates', certificates), ('verification', verification), ('adverse', adverse_results)]:
        (output/(name+'.json')).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    with (output/'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['domain','policy','window','answers','minimum_reused','maximum_reused','always','possible','set_band','continuous_revision'])
        for domain, policies in results.items():
            for policy, record in policies.items():
                for window, value in record['windows'].items():
                    writer.writerow([domain,policy,window,value['answers'],*value['outcomes']['reused'],value['outcomes']['always_reused'],value['outcomes']['possibly_reused'],value['set_band']['reused'],value['references']['continuous_revision']['reused']])
    return {'all_retained_audit_summaries_match': True, 'four_training_optimum_sets': True,
            'ten_complete_decision_partitions_match_direct_rank_formulation': True,
            'seconds': time.monotonic()-started}
