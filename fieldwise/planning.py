"""Time-budgeted visits using OR-Tools with priority-weighted drop penalties."""
import math
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

DEPOT = (-26.05, 28.55)


def estimated_matrix(farms):
    points = [DEPOT] + [(f['latitude'], f['longitude']) for f in farms]
    def minutes(a, b):
        if a == b: return 0
        lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
        h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
        km = 6371 * 2 * math.asin(min(1, math.sqrt(h)))
        return max(1, math.ceil(km * 1.3 / 45 * 60))
    return [[minutes(a, b) for b in points] for a in points]


def plan_visits(farms, budget, matrix=None):
    matrix = estimated_matrix(farms) if matrix is None else matrix
    size = len(farms) + 1
    if len(matrix) != size or any(len(r) != size for r in matrix):
        raise ValueError('Travel matrix must include depot plus every farm.')
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    def transit(a, b):
        source, target = manager.IndexToNode(a), manager.IndexToNode(b)
        service = farms[source-1]['visit_minutes'] if source else 0
        return int(matrix[source][target] + service)
    callback = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    routing.AddDimension(callback, 0, budget, True, 'Time')
    for i, farm in enumerate(farms, 1):
        routing.AddDisjunction([manager.NodeToIndex(i)], int(1000 + 100 * farm['score']))
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(250)
    solution = routing.SolveWithParameters(params)
    if solution is None: raise ValueError('No feasible route found.')
    visits, current = [], routing.Start(0)
    dimension = routing.GetDimensionOrDie('Time')
    while not routing.IsEnd(current):
        node = manager.IndexToNode(current)
        if node:
            farm = farms[node-1]
            visits.append(dict(id=farm['id'], name=farm['name'], score=farm['score'],
                               arrival_minutes=solution.Value(dimension.CumulVar(current)),
                               visit_minutes=farm['visit_minutes']))
        current = solution.Value(routing.NextVar(current))
    seen = {v['id'] for v in visits}
    return {'visits': visits, 'deferred': [f['id'] for f in farms if f['id'] not in seen],
            'total_minutes': solution.Value(dimension.CumulVar(current)), 'budget_minutes': budget,
            'travel_basis': 'Estimate: straight-line distance × 1.3, 45 km/h; not road directions',
            'depot': {'latitude': DEPOT[0], 'longitude': DEPOT[1]}, 'solver': 'OR-Tools'}
