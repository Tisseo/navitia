#include <boost/foreach.hpp>
#include <fstream>
#include <unordered_map>
#include <utils/logger.h>
#include "utils/functions.h"
#include "georef.h"

#include "utils/csv.h"
#include "utils/configuration.h"

using navitia::type::idx_t;

namespace navitia{ namespace georef{

/** Ajout d'une adresse dans la liste des adresses d'une rue
  * les adresses avec un numéro pair sont dans la liste "house_number_right"
  * les adresses avec un numéro impair sont dans la liste "house_number_left"
  * Après l'ajout, la liste est trié dans l'ordre croissant des numéros
*/

void Way::add_house_number(const HouseNumber& house_number){
    if (house_number.number % 2 == 0){
            this->house_number_right.push_back(house_number);
            std::sort(this->house_number_right.begin(),this->house_number_right.end());
    } else{
        this->house_number_left.push_back(house_number);
        std::sort(this->house_number_left.begin(),this->house_number_left.end());
    }
}

/** Recherche des coordonnées les plus proches à un un numéro
    * les coordonnées par extrapolation
*/
nt::GeographicalCoord Way::extrapol_geographical_coord(int number){
    HouseNumber hn_upper, hn_lower;
    nt::GeographicalCoord to_return;

    if (number % 2 == 0){ // pair
        for(auto it=this->house_number_right.begin(); it != this->house_number_right.end(); ++it){
            if ((*it).number  < number){
                hn_lower = (*it);
            }else {
                hn_upper = (*it);
                break;
            }
        }
    }else{
        for(auto it=this->house_number_left.begin(); it != this->house_number_left.end(); ++it){
            if ((*it).number  < number){
                hn_lower = (*it);
            }else {
                hn_upper = (*it);
                break;
            }
        }
    }

    // Extrapolation des coordonnées:
    int diff_house_number = hn_upper.number - hn_lower.number;
    int diff_number = number - hn_lower.number;

    double x_step = (hn_upper.coord.lon() - hn_lower.coord.lon()) /diff_house_number;
    to_return.set_lon(hn_lower.coord.lon() + x_step*diff_number);

    double y_step = (hn_upper.coord.lat() - hn_lower.coord.lat()) /diff_house_number;
    to_return.set_lat(hn_lower.coord.lat() + y_step*diff_number);

    return to_return;
}

/**
    * Si le numéro est plus grand que les numéros, on renvoie les coordonées du plus grand de la rue
    * Si le numéro est plus petit que les numéros, on renvoie les coordonées du plus petit de la rue
    * Si le numéro existe, on renvoie ses coordonnées
    * Sinon, les coordonnées par extrapolation
*/

nt::GeographicalCoord Way::get_geographical_coord(const std::vector< HouseNumber>& house_number_list, const int number){

    if (house_number_list.size() > 0){

        /// Dans le cas où le numéro recherché est plus grand que tous les numéros de liste
        if (house_number_list.back().number <= number){
            return house_number_list.back().coord;
        }

        /// Dans le cas où le numéro recherché est plus petit que tous les numéros de liste
        if (house_number_list.front().number >= number){
            return house_number_list.front().coord;
        }

        /// Dans le cas où le numéro recherché est dans la liste = à un numéro dans la liste
        for(auto it=house_number_list.begin(); it != house_number_list.end(); ++it){
            if ((*it).number  == number){
                return (*it).coord;
             }
        }

        /// Dans le cas où le numéro recherché est dans la liste et <> à tous les numéros
        return extrapol_geographical_coord(number);
    }    
    nt::GeographicalCoord to_return;
    return to_return;
}

/** Recherche des coordonnées les plus proches à un numéro
    * Si la rue n'a pas de numéro, on renvoie son barycentre
*/
nt::GeographicalCoord Way::nearest_coord(const int number, const Graph& graph){
    /// Attention la liste :
    /// "house_number_right" doit contenir les numéros pairs
    /// "house_number_left" doit contenir les numéros impairs
    /// et les deux listes doivent être trier par numéro croissant

    if (( this->house_number_right.empty() && this->house_number_left.empty() )
            || (this->house_number_right.empty() && number % 2 == 0)
            || (this->house_number_left.empty() && number % 2 != 0)
            || number <= 0)
        return barycentre(graph);

    if (number % 2 == 0) // Pair
        return get_geographical_coord(this->house_number_right, number);
    else // Impair
        return get_geographical_coord(this->house_number_left, number);
}

// Calcul du barycentre de la rue
nt::GeographicalCoord Way::barycentre(const Graph& graph){   
    std::vector<nt::GeographicalCoord> line;
    nt::GeographicalCoord centroid;

    std::pair<vertex_t, vertex_t> previous(type::invalid_idx, type::invalid_idx);
    for(auto edge : this->edges){
        if(edge.first != previous.second || edge.second != previous.first ){
            line.push_back(graph[edge.first].coord);
            line.push_back(graph[edge.second].coord);
        }
        previous = edge;
    }
    try{
        boost::geometry::centroid(line, centroid);
    }catch(...){
      LOG4CPLUS_WARN(log4cplus::Logger::getInstance("log") ,"Impossible de trouver le barycentre de la rue :  " + this->name);
    }

    return centroid;
}

/** Recherche du némuro le plus proche à des coordonnées
    * On récupère le numéro se trouvant à une distance la plus petite par rapport aux coordonnées passées en paramètre
*/
int Way::nearest_number(const nt::GeographicalCoord& coord){

    int to_return = -1;
    double distance, distance_temp;
    distance = std::numeric_limits<double>::max();
    for(auto house_number : this->house_number_left){
        distance_temp = coord.distance_to(house_number.coord);
        if (distance  > distance_temp){
            to_return = house_number.number;
            distance = distance_temp;
        }
    }
    for(auto house_number : this->house_number_right){
        distance_temp = coord.distance_to(house_number.coord);
        if (distance  > distance_temp){
            to_return = house_number.number;
            distance = distance_temp;
        }
    }
    return to_return;
}

void GeoRef::init(std::vector<float> &distances, std::vector<vertex_t> &predecessors) const{
    size_t n = boost::num_vertices(this->graph);
    distances.assign(n, std::numeric_limits<float>::max());
    predecessors.resize(n);
}


Path GeoRef::build_path(vertex_t best_destination, std::vector<vertex_t> preds) const {
    Path p;
    std::vector<vertex_t> reverse_path;
    while(best_destination != preds[best_destination]){
        reverse_path.push_back(best_destination);
        best_destination = preds[best_destination];
    }
    reverse_path.push_back(best_destination);

    // On reparcourt tout dans le bon ordre
    nt::idx_t last_way =  type::invalid_idx;
    PathItem path_item;
    p.coordinates.push_back(graph[reverse_path.back()].coord);
    p.length = 0;
    for(size_t i = reverse_path.size(); i > 1; --i){
        vertex_t v = reverse_path[i-2];
        vertex_t u = reverse_path[i-1];
        p.coordinates.push_back(graph[v].coord);

        edge_t e = boost::edge(u, v, graph).first;
        Edge edge = graph[e];
        if(edge.way_idx != last_way && last_way != type::invalid_idx){
            p.path_items.push_back(path_item);
            path_item = PathItem();
        }
        last_way = edge.way_idx;
        path_item.way_idx = edge.way_idx;
        path_item.segments.push_back(e);
        path_item.length += edge.length;
        p.length+= edge.length;
    }
    if(reverse_path.size() > 1)
        p.path_items.push_back(path_item);
    return p;
}

Path GeoRef::compute(std::vector<vertex_t> starts, std::vector<vertex_t> destinations, std::vector<double> start_zeros, std::vector<double> dest_zeros) const {
    if(starts.size() == 0 || destinations.size() == 0)
        throw proximitylist::NotFound();

    if(start_zeros.size() != starts.size())
        start_zeros.assign(starts.size(), 0);

    if(dest_zeros.size() != destinations.size())
        dest_zeros.assign(destinations.size(), 0);

    std::vector<vertex_t> preds;

    // Tableau des distances des nœuds à l'origine, par défaut à l'infini
    std::vector<float> dists;

    this->init(dists, preds);

    for(size_t i = 0; i < starts.size(); ++i){
        vertex_t start = starts[i];
        dists[start] = start_zeros[i];
        // On effectue un Dijkstra sans ré-initialiser les tableaux de distances et de prédécesseur
        try {
            this->dijkstra(start, dists, preds, target_visitor(destinations));
        } catch (DestinationFound) {}
    }

    // On cherche la destination la plus proche
    vertex_t best_destination = destinations.front();
    float best_distance = std::numeric_limits<float>::max();
    for(size_t i = 0; i < destinations.size(); ++i){
        vertex_t destination = destinations[i];
        dists[i] += dest_zeros[i];
        if(dists[destination] < best_distance) {
            best_distance = dists[destination];
            best_destination = destination;
        }
    }

    // Si un chemin existe
    if(best_distance < std::numeric_limits<float>::max()){
        Path p = build_path(best_destination, preds);
        p.length = best_distance;
        return p;
    } else {
        throw proximitylist::NotFound();
    }

}


ProjectionData::ProjectionData(const type::GeographicalCoord & coord, const GeoRef & sn, const proximitylist::ProximityList<vertex_t> &prox){

    edge_t edge;
    found = true;
    try {
        edge = sn.nearest_edge(coord, prox);
    } catch(proximitylist::NotFound) {
        found = false;
        this->source = std::numeric_limits<vertex_t>::max();
        this->target = std::numeric_limits<vertex_t>::max();
    }

    if(found) {
        // On cherche les coordonnées des extrémités de ce segment
        this->source = boost::source(edge, sn.graph);
        this->target = boost::target(edge, sn.graph);
        type::GeographicalCoord vertex1_coord = sn.graph[this->source].coord;
        type::GeographicalCoord vertex2_coord = sn.graph[this->target].coord;
        // On projette le nœud sur le segment
        this->projected = coord.project(vertex1_coord, vertex2_coord).first;
        // On calcule la distance « initiale » déjà parcourue avant d'atteindre ces extrémité d'où on effectue le calcul d'itinéraire
        this->source_distance = projected.distance_to(vertex1_coord);
        this->target_distance = projected.distance_to(vertex2_coord);
    }
}



Path GeoRef::compute(const type::GeographicalCoord & start_coord, const type::GeographicalCoord & dest_coord) const{
    ProjectionData start(start_coord, *this, this->pl);
    ProjectionData dest(dest_coord, *this, this->pl);

    if(start.found && dest.found){
       Path p = compute({start.source, start.target},
                     {dest.source, dest.target},
                     {start.source_distance, start.target_distance},
                     {dest.source_distance, dest.target_distance});

        // On rajoute les bouts de coordonnées manquants à partir et vers le projeté de respectivement le départ et l'arrivée
        p.coordinates.push_front(start.projected);
        p.coordinates.push_back(dest.projected);
        return p;
    } else {
        throw proximitylist::NotFound();
    }
}


std::vector<navitia::type::idx_t> GeoRef::find_admins(const type::GeographicalCoord &coord){
    std::vector<navitia::type::idx_t> to_return;
    navitia::georef::Rect search_rect(coord);

    std::vector<idx_t> result;
    auto callback = [](idx_t id, void* vec)->bool{reinterpret_cast<std::vector<idx_t>*>(vec)->push_back(id); return true;};
    this->rtree.Search(search_rect.min, search_rect.max, callback, &result);
    for(idx_t admin_idx : result) {
        if (boost::geometry::within(coord, admins[admin_idx].boundary)){
            to_return.push_back(admin_idx);
        }
    }
    return to_return;
}

void GeoRef::build_proximity_list(){
    pl.clear(); // vider avant de reconstruire
    BOOST_FOREACH(vertex_t u, boost::vertices(this->graph)){
        pl.add(graph[u].coord, u);
    }
    pl.build();
}

void GeoRef::build_autocomplete_list(){
    int pos = 0;
    for(Way way : ways){
        std::string key="";
        for(auto idx : way.admins){
            Admin admin = admins.at(idx);
            if(key.empty()){                
                key = admin.name;
            }else{
                key = key + " " + admin.name;
            }
        }
        fl_way.add_string(way.way_type +" "+ way.name + " " + key, pos,alias, synonymes);
        pos++;
    }
    fl_way.build();

    //Remplir les poi dans la liste autocompletion
    for(POI poi : pois){
        std::string key="";
        for(auto idx : poi.admins){
            Admin admin = admins.at(idx);
            if(key.empty()){
                key = admin.name;
            }else{
                key = key + " " + admin.name;
            }
        }
        fl_poi.add_string(poi.name + " " + key, poi.idx ,alias, synonymes);
    }
    fl_poi.build();

    // les données administratives
    for(Admin admin : admins){
        fl_admin.add_string(admin.name, admin.idx ,alias, synonymes);
    }
    fl_admin.build();
}


/** Chargement de la liste poitype_map : mappage entre codes externes et idx des POITypes*/
void GeoRef::build_poitypes(){
   for(auto ptype : poitypes){
       this->poitype_map[ptype.uri] = ptype.idx;
   }
}

/** Chargement de la liste poi_map : mappage entre codes externes et idx des POIs*/
void GeoRef::build_pois(){
   for(auto poi : pois){
       this->poi_map[poi.uri] = poi.idx;
   }
}

void GeoRef::build_rtree() {
    typedef boost::geometry::model::box<type::GeographicalCoord> box;
    for(const Admin & admin : this->admins){
        auto envelope = boost::geometry::return_envelope<box>(admin.boundary);
        Rect r(envelope.min_corner().lon(), envelope.min_corner().lat(), envelope.max_corner().lon(), envelope.max_corner().lat());
        this->rtree.Insert(r.min, r.max, admin.idx);
    }
}

/** Normalisation des codes externes des rues*/
void GeoRef::normalize_extcode_way(){
    for(Way & way : ways){
        way.uri = "address:"+ way.uri;
        this->way_map[way.uri] = way.idx;
    }
}


void GeoRef::normalize_extcode_admin(){
    for(Admin& admin : admins){
        admin.uri = "admin" + admin.uri;
        this->admin_map[admin.uri] = admin.idx;
    }
}

/**
    * Recherche les voies avec le nom, ce dernier peut contenir : [Numéro de rue] + [Type de la voie ] + [Nom de la voie] + [Nom de la commune]
        * Exemple : 108 rue victor hugo reims
    * Si le numéro est rensigné, on renvoie les coordonnées les plus proches
    * Sinon le barycentre de la rue
*/
std::vector<nf::Autocomplete<nt::idx_t>::fl_quality> GeoRef::find_ways(const std::string & str, const int nbmax) const{
    std::vector<nf::Autocomplete<nt::idx_t>::fl_quality> to_return;
    boost::tokenizer<> tokens(str);

    int search_number = str_to_int(*tokens.begin());
    std::string search_str;

    if (search_number != -1){
        search_str = "";
        for(auto token : tokens){
            search_str = search_str + " " + token;
        }
    }else{
        search_str = str;
    }
    to_return = fl_way.find_complete(search_str, alias, synonymes, word_weight, nbmax);

    /// récupération des coordonnées du numéro recherché pour chaque rue
    for(auto &result_item  : to_return){
       Way way = this->ways[result_item.idx];
       result_item.coord = way.nearest_coord(search_number, this->graph);
       result_item.house_number = search_number;
    }

    return to_return;
}

int GeoRef::project_stop_points(const std::vector<type::StopPoint> & stop_points){
    int matched = 0;
    this->projected_stop_points.reserve(stop_points.size());
    for(type::StopPoint stop_point : stop_points){
        ProjectionData proj(stop_point.coord, *this, this->pl);
        this->projected_stop_points.push_back(proj);
        if(proj.found)
            matched++;
    }
    return matched;
}

edge_t GeoRef::nearest_edge(const type::GeographicalCoord & coordinates) const {
    return this->nearest_edge(coordinates, this->pl);
}


edge_t GeoRef::nearest_edge(const type::GeographicalCoord & coordinates, const proximitylist::ProximityList<vertex_t> &prox) const {
    vertex_t u;
    try {
        u = prox.find_nearest(coordinates);
    } catch(proximitylist::NotFound) {
        throw proximitylist::NotFound();
    }

    type::GeographicalCoord coord_u, coord_v;
    coord_u = this->graph[u].coord;
    float dist = std::numeric_limits<float>::max();
    edge_t best;
    bool found = false;
    BOOST_FOREACH(edge_t e, boost::out_edges(u, this->graph)){
        vertex_t v = boost::target(e, this->graph);
        coord_v = this->graph[v].coord;
        // Petite approximation de la projection : on ne suit pas le tracé de la voirie !
        auto projected = coordinates.project(coord_u, coord_v);
        if(projected.second < dist){
            found = true;
            dist = projected.second;
            best = e;
        }
    }
    if(!found)
        throw proximitylist::NotFound();
    else
        return best;
}
}}
